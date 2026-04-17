const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');

const VIRTUOSO_ENDPOINT = 'https://health.semic.eu/virtuoso/sparql';
const app = express();
const PORT = process.env.PORT || 4000;
const BASE_PATH = '/semantic-registry';

const GRAPH1 = 'http://semic.registry.eu';
const GRAPH2 = 'http://semic.registry2.eu';

const PREFIXES = `
  PREFIX adms: <http://www.w3.org/ns/adms#>
  PREFIX dcat: <http://www.w3.org/ns/dcat#>
  PREFIX dct:  <http://purl.org/dc/terms/>
  PREFIX foaf: <http://xmlns.com/foaf/0.1/>
  PREFIX cv:   <http://data.europa.eu/m8g/>
  PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
  PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
`;

// Language preference: English > untagged > first available
// literals: array of RDF term objects with .value and .language, may contain nulls/undefined
function pickLang(literals) {
  const vals = literals.filter(v => v != null);
  return (
    vals.find(v => v.language === 'en')?.value ??
    vals.find(v => v.language === '')?.value ??
    vals[0]?.value ?? null
  );
}

// Collect distinct non-null .value strings from an array of rows for a given field name
function colStrings(rows, field) {
  return [...new Set(rows.map(r => r[field]?.value).filter(Boolean))];
}

let SparqlClient;

async function initializeSparqlClient() {
  const module = await import('sparql-http-client');
  SparqlClient = module.default;
}

function createClient() {
  return new SparqlClient({
    endpointUrl: VIRTUOSO_ENDPOINT,
    updateUrl: VIRTUOSO_ENDPOINT,
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
}

app.set('trust proxy', true);
app.use(cors());
app.use(bodyParser.json());

app.get('/', (req, res) => {
  res.redirect(301, BASE_PATH + '/');
});

app.get('/health', (req, res) => {
  res.status(200).json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.use((req, res, next) => {
  if (req.path.startsWith(BASE_PATH) || req.path === '/health') {
    return next();
  }
  if (req.path.startsWith('/api/')) {
    return res.redirect(301, BASE_PATH + req.path);
  }
  if (req.path.match(/\.(js|css|png|jpg|jpeg|gif|ico|svg)$/)) {
    return res.redirect(301, BASE_PATH + req.path);
  }
  if (req.path !== '/') {
    return res.redirect(301, BASE_PATH + req.path);
  }
  next();
});

// --- Registry summary stats (1-hour server-side cache) ---
let _statsCache = null;
let _statsCacheAt = 0;

app.get(BASE_PATH + '/api/stats', async (_req, res) => {
  if (_statsCache && (Date.now() - _statsCacheAt) < 3_600_000) {
    return res.json(_statsCache);
  }
  if (!SparqlClient) {
    return res.status(500).json({ error: 'SPARQL client not initialized' });
  }
  const client = createClient();
  function runSelect(q) {
    return new Promise((resolve, reject) => {
      const stream = client.query.select(q, { operation: 'postUrlencoded' });
      const rows = [];
      stream.on('data', r => rows.push(r));
      stream.on('end', () => resolve(rows));
      stream.on('error', reject);
    });
  }
  try {
    const [r1, r2, r3] = await Promise.all([
      runSelect(`SELECT (COUNT(DISTINCT ?a) AS ?n) WHERE {
        GRAPH <${GRAPH1}> { ?a a <http://www.w3.org/ns/adms#Asset> } }`),
      runSelect(`SELECT (COUNT(DISTINCT ?loc) AS ?n) WHERE {
        GRAPH <${GRAPH1}> {
          ?a a <http://www.w3.org/ns/adms#Asset> .
          ?a <http://purl.org/dc/terms/creator> ?c .
          ?c <http://purl.org/dc/terms/spatial> ?loc .
        } }`),
      runSelect(`SELECT (COUNT(DISTINCT ?t) AS ?n) WHERE {
        { GRAPH <${GRAPH1}> { [] <http://www.w3.org/ns/dcat#theme> ?t } }
        UNION
        { GRAPH <${GRAPH2}> { [] <http://www.w3.org/ns/dcat#theme> ?t } }
      }`),
    ]);
    _statsCache = {
      ontologies:   parseInt(r1[0]?.n?.value ?? 0),
      memberStates: parseInt(r2[0]?.n?.value ?? 0),
      dataDomains:  parseInt(r3[0]?.n?.value ?? 0),
    };
    _statsCacheAt = Date.now();
    res.json(_statsCache);
  } catch (err) {
    console.error('Stats SPARQL error:', err);
    res.status(500).json({ error: 'Failed to fetch stats' });
  }
});

app.post(BASE_PATH + '/api/search', async (req, res) => {
  if (!SparqlClient) {
    return res.status(500).json({ error: 'SPARQL client not initialized' });
  }

  const { query, theme, publisher } = req.body;

  if (!query || typeof query !== 'string') {
    return res.status(400).json({ error: 'Missing or invalid search query' });
  }

  const isUri = query.startsWith('http://') || query.startsWith('https://');

  // Theme: check both graphs (graph 2 is fallback — assets may only have themes there)
  const themePattern = theme ? `
    FILTER EXISTS {
      { GRAPH <${GRAPH1}> { ?asset dcat:theme <${theme}> . } }
      UNION
      { GRAPH <${GRAPH2}> { ?asset dcat:theme <${theme}> . } }
    }` : '';
  const publisherPattern = publisher ? `?asset dct:creator <${publisher}> .` : '';

  const client = createClient();

  function runSelect(sparqlQuery) {
    return new Promise((resolve, reject) => {
      const stream = client.query.select(sparqlQuery, { operation: 'postUrlencoded' });
      const rows = [];
      stream.on('data', row => rows.push(row));
      stream.on('end', () => resolve(rows));
      stream.on('error', reject);
    });
  }

  // Q1-match: find matching asset URIs only — no metadata, no joins.
  // Text search covers graph 1 (title, description, class labels) and
  // graph 2 (skos:altLabel, translated descriptions) with equal priority.
  const q1match = `${PREFIXES}
    SELECT DISTINCT ?asset ?lovRank
    WHERE {
      GRAPH <${GRAPH1}> {
        ?asset a adms:Asset .
        OPTIONAL { ?asset cv:lovRank ?lovRank . }
        ${isUri ? `FILTER(?asset = <${query}>)` : ''}
        ${publisherPattern}
      }
      ${themePattern}
      ${!isUri && query && query !== '*' ? `
        OPTIONAL { GRAPH <${GRAPH1}> { ?asset dct:title ?searchTitle . } }
        OPTIONAL { GRAPH <${GRAPH1}> { ?asset dct:description ?searchDesc . } }
        OPTIONAL {
          GRAPH <${GRAPH1}> {
            ?asset dcat:distribution ?searchDist .
            ?searchDist a adms:AssetDistribution .
            ?searchClass a rdfs:Class ;
                         rdfs:isDefinedBy ?searchDist ;
                         rdfs:label ?searchClassName .
          }
        }
        OPTIONAL { GRAPH <${GRAPH2}> { ?asset skos:altLabel ?searchAltLabel . } }
        OPTIONAL { GRAPH <${GRAPH2}> { ?asset dct:description ?searchDesc2 . } }
        FILTER(
          CONTAINS(LCASE(STR(?searchTitle)),     "${query.toLowerCase()}") ||
          CONTAINS(LCASE(STR(?searchDesc)),      "${query.toLowerCase()}") ||
          CONTAINS(LCASE(STR(?searchClassName)), "${query.toLowerCase()}") ||
          CONTAINS(LCASE(STR(?searchAltLabel)), "${query.toLowerCase()}") ||
          CONTAINS(LCASE(STR(?searchDesc2)),    "${query.toLowerCase()}")
        )` : ''}
    }
    ORDER BY DESC(?lovRank)
    LIMIT 50
  `;

  try {
    const matchRows = await runSelect(q1match);

    if (matchRows.length === 0) {
      return res.json([]);
    }

    const valuesList = matchRows.map(r => `<${r.asset.value}>`).join(' ');

    // Q2-meta: raw display metadata — no language filter, no GROUP_CONCAT, no GROUP BY
    // Returns one row per (asset × title × description × publisherNode × publisherName language variant);
    // JS groups and applies language preference.
    const q2meta = `${PREFIXES}
      SELECT ?asset ?title ?description ?publisherNode ?publisherName
      WHERE {
        VALUES ?asset { ${valuesList} }
        GRAPH <${GRAPH1}> {
          ?asset a adms:Asset .
          OPTIONAL { ?asset dct:title ?title }
          OPTIONAL { ?asset dct:description ?description }
          OPTIONAL {
            ?asset dct:creator ?publisherNode .
            OPTIONAL { ?publisherNode foaf:name ?publisherName }
          }
        }
      }
    `;

    // Q3-require: raw requiring-asset relations — no language filter, no GROUP_CONCAT
    const q3require = `${PREFIXES}
      SELECT ?asset ?requiringAsset ?requiringTitle
             ?requiringPublisher ?requiringPublisherName ?requiringLocation
      WHERE {
        VALUES ?asset { ${valuesList} }
        GRAPH <${GRAPH1}> {
          ?asset cv:isReusedBy ?requiringAsset .
          OPTIONAL { ?requiringAsset dct:title ?requiringTitle }
          OPTIONAL {
            ?requiringAsset dct:creator ?requiringPublisher .
            OPTIONAL { ?requiringPublisher foaf:name ?requiringPublisherName }
          }
          OPTIONAL {
            ?requiringAsset dct:creator ?requiringAgent .
            ?requiringAgent dct:spatial ?requiringLocation .
          }
        }
      }
    `;

    const [metaRows, reqRows] = await Promise.all([
      runSelect(q2meta),
      runSelect(q3require)
    ]);

    // Group metadata rows by asset URI
    // publishers: Map<publisherNodeUri, langLiteral[]> so pickLang can be applied per node
    const metaByAsset = new Map();
    for (const row of metaRows) {
      const uri = row.asset.value;
      if (!metaByAsset.has(uri)) {
        metaByAsset.set(uri, { titles: [], descriptions: [], publishers: new Map() });
      }
      const entry = metaByAsset.get(uri);
      if (row.title)       entry.titles.push(row.title);
      if (row.description) entry.descriptions.push(row.description);
      if (row.publisherName && row.publisherNode) {
        const nodeUri = row.publisherNode.value;
        if (!entry.publishers.has(nodeUri)) entry.publishers.set(nodeUri, []);
        entry.publishers.get(nodeUri).push(row.publisherName);
      }
    }

    // Group requiring-asset rows by asset URI, then by requiring asset URI
    // publisherNames: Map<publisherNodeUri, langLiteral[]> so pickLang can be applied per node
    const reqByAsset = new Map();
    for (const row of reqRows) {
      const uri    = row.asset.value;
      const reqUri = row.requiringAsset.value;
      if (!reqByAsset.has(uri)) reqByAsset.set(uri, new Map());
      const reqMap = reqByAsset.get(uri);
      if (!reqMap.has(reqUri)) {
        reqMap.set(reqUri, { uri: reqUri, titles: [], publisherNames: new Map(), locations: new Set() });
      }
      const entry = reqMap.get(reqUri);
      if (row.requiringTitle) entry.titles.push(row.requiringTitle);
      if (row.requiringPublisherName && row.requiringPublisher) {
        const nodeUri = row.requiringPublisher.value;
        if (!entry.publisherNames.has(nodeUri)) entry.publisherNames.set(nodeUri, []);
        entry.publisherNames.get(nodeUri).push(row.requiringPublisherName);
      }
      if (row.requiringLocation) entry.locations.add(row.requiringLocation.value);
    }

    const results = matchRows.map(row => {
      const uri  = row.asset.value;
      const meta = metaByAsset.get(uri) || { titles: [], descriptions: [], publishers: new Map() };
      const reqMap = reqByAsset.get(uri);

      const requiringAssets = reqMap
        ? [...reqMap.values()].map(r => ({
            uri:       r.uri,
            title:     pickLang(r.titles) ?? '',
            publisher: pickLang([...r.publisherNames.values()][0] ?? []) ?? ''
          }))
        : [];

      const requiringPublisherNames = reqMap
        ? [...new Set(
            [...reqMap.values()].flatMap(r =>
              [...r.publisherNames.values()].map(names => pickLang(names)).filter(Boolean)
            )
          )]
        : [];

      const requiringLocations = reqMap
        ? [...new Set([...reqMap.values()].flatMap(r => [...r.locations]))]
        : [];

      return {
        uri,
        title:                  pickLang(meta.titles),
        description:            pickLang(meta.descriptions),
        publishers:             [...meta.publishers.values()].map(names => pickLang(names)).filter(Boolean),
        ranking:                row.lovRank?.value ?? null,
        mainClasses:            [],
        reusedOntologies:       [],
        requiringAssets,
        requiringPublisherNames,
        requiringLocations,
        keywords:               [],
        created:                null,
        homepage:               null,
        languages:              [],
        distributions:          [],
        dataThemes:             []
      };
    });

    res.json(results);
  } catch (err) {
    console.error('SPARQL error:', err);
    console.error('\nSPARQL query:\n');
    res.status(500).json({ error: 'SPARQL query failed', details: err.message });
  }
});

app.post(BASE_PATH + '/api/ontology', async (req, res) => {
  if (!SparqlClient) {
    return res.status(500).json({ error: 'SPARQL client not initialized' });
  }

  const { slug } = req.body;
  if (!slug || typeof slug !== 'string') {
    return res.status(400).json({ error: 'Missing or invalid slug' });
  }

  const isUri = slug.startsWith('http://') || slug.startsWith('https://');

  const client = createClient();

  function runSelect(sparqlQuery) {
    return new Promise((resolve, reject) => {
      const stream = client.query.select(sparqlQuery, { operation: 'postUrlencoded' });
      const rows = [];
      stream.on('data', row => rows.push(row));
      stream.on('end', () => resolve(rows));
      stream.on('error', reject);
    });
  }

  // Resolve slug → asset URI; match titles in any language (JS handles preference later)
  let assetUri = null;
  if (isUri) {
    assetUri = slug;
  } else {
    // Normalise slug in JS; LCASE() in SPARQL lowercases the stored title for comparison
    const normalised = slug.replace(/-/g, ' ').toLowerCase();
    const resolveQuery = `${PREFIXES}
      SELECT ?asset WHERE {
        GRAPH <http://semic.registry.eu> {
          ?asset a adms:Asset .
          ?asset dct:title ?title .
          FILTER(LCASE(STR(?title)) = "${normalised}")
        }
      }
      LIMIT 1
    `;

    try {
      const resolveRows = await runSelect(resolveQuery);
      assetUri = resolveRows[0]?.asset?.value ?? null;
    } catch (err) {
      console.error('SPARQL resolve error:', err);
      return res.status(500).json({ error: 'Failed to resolve slug', details: err.message });
    }

    if (!assetUri) {
      return res.status(404).json({ error: 'Ontology not found' });
    }
  }

  // Q1a: Scalar fields only — no multi-value OPTIONALs, avoids Cartesian product with titles/descriptions.
  // LIMIT 1 is safe because lovRank/created/homepage are expected to be single-valued per asset.
  const q1scalar = `${PREFIXES}
    SELECT ?lovRank ?created ?homepage
    WHERE {
      BIND(<${assetUri}> AS ?asset)
      GRAPH <${GRAPH1}> {
        ?asset a adms:Asset .
        OPTIONAL { ?asset cv:lovRank ?lovRank }
        OPTIONAL { ?asset dct:created ?created }
        OPTIONAL { ?asset foaf:homepage ?homepage }
      }
    }
    LIMIT 1
  `;

  // Q1b: Multi-value text fields — title and description language variants only.
  const q1text = `${PREFIXES}
    SELECT ?title ?description
    WHERE {
      BIND(<${assetUri}> AS ?asset)
      GRAPH <${GRAPH1}> {
        ?asset a adms:Asset .
        OPTIONAL { ?asset dct:title ?title }
        OPTIONAL { ?asset dct:description ?description }
      }
    }
  `;

  // Q2: Publishers — raw rows, one per (publisherNode × publisherName language variant)
  const q2 = `${PREFIXES}
    SELECT ?publisherNode ?publisherName
    WHERE {
      BIND(<${assetUri}> AS ?asset)
      GRAPH <${GRAPH1}> {
        ?asset dct:creator ?publisherNode .
        OPTIONAL { ?publisherNode foaf:name ?publisherName }
      }
    }
  `;

  // Q3: Keywords and languages from graph 1 — raw rows, JS deduplicates
  const q3 = `${PREFIXES}
    SELECT ?keyword ?languageUri
    WHERE {
      BIND(<${assetUri}> AS ?asset)
      GRAPH <${GRAPH1}> {
        OPTIONAL { ?asset dcat:keyword ?keyword }
        OPTIONAL { ?asset dct:language ?languageUri }
      }
    }
  `;

  // Q3themes: Data themes — graph 1 primary, graph 2 as fallback when graph 1 has none
  const q3themes = `${PREFIXES}
    SELECT DISTINCT ?dataTheme
    WHERE {
      BIND(<${assetUri}> AS ?asset)
      {
        GRAPH <${GRAPH1}> { ?asset dcat:theme ?dataTheme . }
      }
      UNION
      {
        FILTER NOT EXISTS { GRAPH <${GRAPH1}> { ?asset dcat:theme [] . } }
        GRAPH <${GRAPH2}> { ?asset dcat:theme ?dataTheme . }
      }
    }
  `;

  // Q4: Distributions — raw rows, JS deduplicates by download URL
  const q4 = `${PREFIXES}
    SELECT ?downloadURL ?format
    WHERE {
      BIND(<${assetUri}> AS ?asset)
      GRAPH <${GRAPH1}> {
        ?asset dcat:distribution ?distDl .
        ?distDl a adms:AssetDistribution ;
                dcat:downloadURL ?downloadURL .
        OPTIONAL { ?distDl dct:format ?format }
      }
    }
  `;

  // Q5: Classes via distributions — raw rows, JS groups by class URI and picks language
  const q5 = `${PREFIXES}
    SELECT ?class ?className
    WHERE {
      BIND(<${assetUri}> AS ?asset)
      GRAPH <${GRAPH1}> {
        ?asset dcat:distribution ?dist .
        ?dist a adms:AssetDistribution .
        ?class a rdfs:Class ;
               rdfs:isDefinedBy ?dist ;
               rdfs:label ?className .
      }
    }
  `;

  // Q6: Reused ontologies (dct:requires outbound) — raw rows, JS groups by reused URI
  const q6 = `${PREFIXES}
    SELECT ?reused ?reusedTitle
    WHERE {
      BIND(<${assetUri}> AS ?asset)
      GRAPH <${GRAPH1}> {
        ?asset dct:requires ?reused .
        OPTIONAL { ?reused dct:title ?reusedTitle }
      }
    }
  `;

  // Q7: Assets that reuse this asset (cv:isReusedBy outbound) — raw rows
  const q7 = `${PREFIXES}
    SELECT ?requiringAsset ?requiringTitle
           ?requiringPublisher ?requiringPublisherName ?requiringLocation
    WHERE {
      BIND(<${assetUri}> AS ?asset)
      GRAPH <${GRAPH1}> {
        ?asset cv:isReusedBy ?requiringAsset .
        OPTIONAL { ?requiringAsset dct:title ?requiringTitle }
        OPTIONAL {
          ?requiringAsset dct:creator ?requiringPublisher .
          OPTIONAL { ?requiringPublisher foaf:name ?requiringPublisherName }
        }
        OPTIONAL {
          ?requiringAsset dct:creator ?requiringAgent .
          ?requiringAgent dct:spatial ?requiringLocation .
        }
      }
    }
  `;

  try {
    const [rows1scalar, rows1text, rows2, rows3, rows3themes, rows4, rows5, rows6, rows7] = await Promise.all([
      runSelect(q1scalar), runSelect(q1text), runSelect(q2), runSelect(q3), runSelect(q3themes),
      runSelect(q4), runSelect(q5), runSelect(q6), runSelect(q7)
    ]);

    if (rows1scalar.length === 0 && rows1text.length === 0) {
      return res.status(404).json({ error: 'Ontology not found' });
    }

    // Q1 assembly — scalars from dedicated query; text from separate query to avoid Cartesian product
    const title       = pickLang(rows1text.map(r => r.title).filter(Boolean));
    const description = pickLang(rows1text.map(r => r.description).filter(Boolean));
    const lovRank     = rows1scalar[0]?.lovRank?.value  ?? null;
    const created     = rows1scalar[0]?.created?.value  ?? null;
    const homepage    = rows1scalar[0]?.homepage?.value ?? null;

    // Q2 assembly — group by publisherNode, pick best language name per node
    const pubMap = new Map();
    for (const row of rows2) {
      const nodeUri = row.publisherNode.value;
      if (!pubMap.has(nodeUri)) pubMap.set(nodeUri, []);
      if (row.publisherName) pubMap.get(nodeUri).push(row.publisherName);
    }
    const publishers = [...pubMap.values()]
      .map(names => pickLang(names))
      .filter(Boolean);

    // Q3 assembly — deduplicate URIs/strings
    const keywords   = colStrings(rows3, 'keyword');
    const languages  = colStrings(rows3, 'languageUri');
    // Q3themes: graph 1 primary, graph 2 fallback (already resolved by SPARQL UNION/FILTER NOT EXISTS)
    const dataThemes = colStrings(rows3themes, 'dataTheme');

    // Q4 assembly — deduplicate by download URL
    const distMap = new Map();
    for (const row of rows4) {
      const url = row.downloadURL.value;
      if (!distMap.has(url)) distMap.set(url, row.format?.value ?? null);
    }
    const distributions = [...distMap.entries()].map(([url, format]) => ({ url, format }));

    // Q5 assembly — group by class URI, pick best language label; keep URI for prefix display
    const classMap = new Map();
    for (const row of rows5) {
      const classUri = row.class.value;
      if (!classMap.has(classUri)) classMap.set(classUri, []);
      if (row.className) classMap.get(classUri).push(row.className);
    }
    const mainClasses = [...classMap.entries()]
      .map(([uri, names]) => ({ uri, label: pickLang(names) }))
      .filter(entry => entry.uri);

    // Q6 assembly — group by reused URI, pick best language title
    const reusedMap = new Map();
    for (const row of rows6) {
      const uri = row.reused.value;
      if (!reusedMap.has(uri)) reusedMap.set(uri, []);
      if (row.reusedTitle) reusedMap.get(uri).push(row.reusedTitle);
    }
    const reusedOntologies = [...reusedMap.entries()].map(([uri, titles]) => ({
      uri,
      title: pickLang(titles) ?? ''
    }));

    // Q7 assembly — group by requiring asset URI
    // publisherNames: Map<publisherNodeUri, langLiteral[]> so pickLang can be applied per node
    const reqMap7 = new Map();
    for (const row of rows7) {
      const uri = row.requiringAsset.value;
      if (!reqMap7.has(uri)) {
        reqMap7.set(uri, { titles: [], publisherNames: new Map(), locations: new Set() });
      }
      const entry = reqMap7.get(uri);
      if (row.requiringTitle) entry.titles.push(row.requiringTitle);
      if (row.requiringPublisherName && row.requiringPublisher) {
        const nodeUri = row.requiringPublisher.value;
        if (!entry.publisherNames.has(nodeUri)) entry.publisherNames.set(nodeUri, []);
        entry.publisherNames.get(nodeUri).push(row.requiringPublisherName);
      }
      if (row.requiringLocation) entry.locations.add(row.requiringLocation.value);
    }
    const requiringAssets = [...reqMap7.entries()].map(([uri, data]) => ({
      uri,
      title:     pickLang(data.titles) ?? '',
      publisher: pickLang([...data.publisherNames.values()][0] ?? []) ?? ''
    }));
    const requiringPublisherNames = [...new Set(
      [...reqMap7.values()].flatMap(d =>
        [...d.publisherNames.values()].map(names => pickLang(names)).filter(Boolean)
      )
    )];
    const requiringLocations = [...new Set(
      [...reqMap7.values()].flatMap(d => [...d.locations])
    )];

    res.json({
      uri: assetUri,
      title,
      description,
      ranking: lovRank,
      created,
      homepage,
      publishers,
      keywords,
      languages,
      dataThemes,
      distributions,
      mainClasses,
      reusedOntologies,
      requiringAssets,
      requiringPublisherNames,
      requiringLocations
    });
  } catch (err) {
    console.error('SPARQL error:', err);
    console.error('\nSPARQL query:\n');
    res.status(500).json({ error: 'SPARQL query failed', details: err.message });
  }
});

app.use(BASE_PATH, express.static(path.join(__dirname, 'public')));

app.use(BASE_PATH + '/proxy/*', createProxyMiddleware({
  target: 'https://health.semic.eu',
  changeOrigin: true,
  pathRewrite: {
    [`^${BASE_PATH}/proxy`]: ''
  }
}));

app.get(BASE_PATH + '*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('*', (req, res) => {
  res.redirect(BASE_PATH + '/');
});

async function startServer() {
  try {
    await initializeSparqlClient();
    console.log('SPARQL client initialized');
    app.listen(PORT, '0.0.0.0', () => {
      console.log(`Server with reverse proxy running on http://0.0.0.0:${PORT}`);
    });
  } catch (error) {
    console.error('Failed to initialize server:', error);
    process.exit(1);
  }
}

startServer();
