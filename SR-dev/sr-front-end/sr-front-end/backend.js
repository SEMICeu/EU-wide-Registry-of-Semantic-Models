const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const SparqlClient = require('sparql-http-client').default;

const VIRTUOSO_ENDPOINT = 'http://63.32.50.253:81/sparql';
const app = express();
const PORT = 4000;

app.use(cors());
app.use(bodyParser.json());

app.post('/api/search', async (req, res) => {
  const { query, theme } = req.body;

  if (!query || typeof query !== 'string') {
    return res.status(400).json({ error: 'Missing or invalid search query' });
  }

  // Check if query is a URI
  const isUri = query.startsWith('http://') || query.startsWith('https://');

  // Add theme filter dynamically if provided
  const themeFilter = theme
    ? `FILTER(?dataTheme = <${theme}>)`
    : '';

  const sparqlQuery = `
    PREFIX dct: <http://purl.org/dc/terms/>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX prof: <http://www.w3.org/ns/dx/prof/>
    SELECT ?title ?description ?lovRank
      (GROUP_CONCAT(DISTINCT COALESCE(?publisherName, STR(?publisher)); SEPARATOR="||") AS ?publishers)
      (GROUP_CONCAT(DISTINCT ?classLabel; SEPARATOR="||") AS ?mainClasses)
      (GROUP_CONCAT(DISTINCT CONCAT(STR(?reused), "|", COALESCE(?reusedTitle, "")); SEPARATOR="||") AS ?reusedOntologies)
      (GROUP_CONCAT(DISTINCT ?keyword; SEPARATOR="||") AS ?keywords)
      ?created ?homepage
      (GROUP_CONCAT(DISTINCT ?language; SEPARATOR="||") AS ?languages)
      (GROUP_CONCAT(DISTINCT CONCAT(STR(?downloadURL), "|", COALESCE(STR(?format), "")); SEPARATOR="||") AS ?distributions)
      (GROUP_CONCAT(DISTINCT ?dataTheme; SEPARATOR="||") AS ?dataThemes)
    FROM <http://semic.registry.eu>
    WHERE {
      {
        SELECT DISTINCT ?standard
        WHERE {
          ?standard a dct:Standard .
          ?standard dct:title ?title .
          ?standard dct:description ?description .
          OPTIONAL {
            ?standard dct:hasPart ?class .
            ?class a rdfs:Class ;
                  rdfs:label ?classLabel .
            FILTER(lang(?classLabel) = "en")
          }
          FILTER (lang(?title) = "en")
          FILTER (lang(?description) = "en")
          ${isUri ?
            `FILTER(?standard = <${query}>)` :
            `FILTER(
              CONTAINS(LCASE(?title), LCASE("${query}")) ||
              CONTAINS(LCASE(?description), LCASE("${query}")) ||
              CONTAINS(LCASE(?classLabel), LCASE("${query}"))
            )`
          }
        }
      }
      ?standard dct:title ?title .
      ?standard dct:description ?description .
      ?standard dct:publisher ?publisher .
      OPTIONAL {
        ?publisher a foaf:Agent ;
                  dct:title ?publisherName .
        FILTER(lang(?publisherName) = "en")
      }
      OPTIONAL {
        ?standard dct:hasPart ?class .
        ?class a rdfs:Class ;
              rdfs:label ?classLabel .
        FILTER(lang(?classLabel) = "en")
      }
      OPTIONAL {
        ?standard dct:requires ?reused .
        OPTIONAL { ?reused dct:title ?reusedTitle . FILTER(lang(?reusedTitle) = "en") }
      }
      OPTIONAL { ?standard dcat:keyword ?keyword }
      OPTIONAL { ?standard dct:created ?created }
      OPTIONAL { ?standard foaf:homepage ?homepage }
      OPTIONAL { ?standard dct:language ?language }
      OPTIONAL {
        ?standard prof:hasResource ?resourceDescriptor .
        ?resourceDescriptor dcat:downloadURL ?downloadURL .
        OPTIONAL { ?resourceDescriptor dct:format ?format }
      }
      OPTIONAL { ?standard dcat:theme ?dataTheme }  # <-- added
      ?standard <http://example.org/LOVRank> ?lovRank .
      FILTER (lang(?title) = "en")
      FILTER (lang(?description) = "en")
      ${themeFilter}  # <-- added
    }
    GROUP BY ?title ?description ?lovRank ?created ?homepage
    LIMIT 50
  `;

  const client = new SparqlClient({ endpointUrl: VIRTUOSO_ENDPOINT });

  try {
    const stream = client.query.select(sparqlQuery);
    const results = [];
    stream.on('data', row => {
      results.push({
        title: row.title.value,
        description: row.description.value,
        publishers: row.publishers ? row.publishers.value.split('||') : [],
        ranking: row.lovRank.value,
        mainClasses: row.mainClasses ? row.mainClasses.value.split('||') : [],
        reusedOntologies: row.reusedOntologies
          ? row.reusedOntologies.value.split('||').filter(Boolean).map(str => {
              const [uri, title] = str.split('|');
              return { uri, title };
            })
          : [],
        keywords: row.keywords ? row.keywords.value.split('||') : [],
        created: row.created ? row.created.value : null,
        homepage: row.homepage ? row.homepage.value : null,
        languages: row.languages ? row.languages.value.split('||') : [],
        distributions: row.distributions
          ? row.distributions.value.split('||').filter(Boolean).map(str => {
              const [url, format] = str.split('|');
              return { url, format };
            })
          : [],
        dataThemes: row.dataThemes ? row.dataThemes.value.split('||') : []
      });
    });
    stream.on('end', () => res.json(results));
    stream.on('error', err => {
      console.error('SPARQL error:', err);
      res.status(500).json({ error: 'SPARQL query failed', details: err.message });
    });
  } catch (err) {
    console.error('SPARQL error:', err);
    res.status(500).json({ error: 'SPARQL query failed', details: err.message });
  }
});

app.post('/api/ontology', async (req, res) => {
  const { slug } = req.body;
  if (!slug || typeof slug !== 'string') {
    return res.status(400).json({ error: 'Missing or invalid slug' });
  }

  // Check if slug is actually a URI
  const isUri = slug.startsWith('http://') || slug.startsWith('https://');

  const sparqlQuery = `
    PREFIX dct: <http://purl.org/dc/terms/>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX prof: <http://www.w3.org/ns/dx/prof/>
    SELECT ?title ?description ?lovRank
      (GROUP_CONCAT(DISTINCT COALESCE(?publisherName, STR(?publisher)); SEPARATOR="||") AS ?publishers)
      (GROUP_CONCAT(DISTINCT ?classLabel; SEPARATOR="||") AS ?mainClasses)
      (GROUP_CONCAT(DISTINCT CONCAT(STR(?reused), "|", COALESCE(?reusedTitle, "")); SEPARATOR="||") AS ?reusedOntologies)
      (GROUP_CONCAT(DISTINCT ?keyword; SEPARATOR="||") AS ?keywords)
      ?created ?homepage
      (GROUP_CONCAT(DISTINCT ?language; SEPARATOR="||") AS ?languages)
      (GROUP_CONCAT(DISTINCT CONCAT(STR(?downloadURL), "|", COALESCE(STR(?format), "")); SEPARATOR="||") AS ?distributions)
      (GROUP_CONCAT(DISTINCT ?dataTheme; SEPARATOR="||") AS ?dataThemes)
    FROM <http://semic.registry.eu>
    WHERE {
      ?standard a dct:Standard .
      ?standard dct:title ?title .
      ?standard dct:description ?description .
      ?standard dct:publisher ?publisher .
      OPTIONAL {
        ?publisher a foaf:Agent ;
                  dct:title ?publisherName .
        FILTER(lang(?publisherName) = "en")
      }
      OPTIONAL {
        ?standard dct:hasPart ?class .
        ?class a rdfs:Class ;
              rdfs:label ?classLabel .
        FILTER(lang(?classLabel) = "en")
      }
      OPTIONAL {
        ?standard dct:requires ?reused .
        OPTIONAL { ?reused dct:title ?reusedTitle . FILTER(lang(?reusedTitle) = "en") }
      }
      OPTIONAL { ?standard dcat:keyword ?keyword }
      OPTIONAL { ?standard dct:created ?created }
      OPTIONAL { ?standard foaf:homepage ?homepage }
      OPTIONAL { ?standard dct:language ?language }
      OPTIONAL {
        ?standard prof:hasResource ?resourceDescriptor .
        ?resourceDescriptor dcat:downloadURL ?downloadURL .
        OPTIONAL { ?resourceDescriptor dct:format ?format }
      }
      OPTIONAL { ?standard dcat:theme ?dataTheme }
      ?standard <http://example.org/LOVRank> ?lovRank .
      FILTER (lang(?title) = "en")
      FILTER (lang(?description) = "en")
      ${isUri ?
        `FILTER(?standard = <${slug}>)` :
        `FILTER(REPLACE(LCASE(?title), "[^a-z0-9]+", "-", "g") = "${slug}")`
      }
    }
    GROUP BY ?title ?description ?lovRank ?created ?homepage
    LIMIT 1
  `;

  const client = new SparqlClient({ endpointUrl: VIRTUOSO_ENDPOINT });

  try {
    const stream = client.query.select(sparqlQuery);
    let found = null;
    stream.on('data', row => {
      found = {
        title: row.title.value,
        description: row.description.value,
        publishers: row.publishers ? row.publishers.value.split('||') : [],
        ranking: row.lovRank.value,
        mainClasses: row.mainClasses ? row.mainClasses.value.split('||') : [],
        reusedOntologies: row.reusedOntologies
          ? row.reusedOntologies.value.split('||').filter(Boolean).map(str => {
              const [uri, title] = str.split('|');
              return { uri, title };
            })
          : [],
        keywords: row.keywords ? row.keywords.value.split('||') : [],
        created: row.created ? row.created.value : null,
        homepage: row.homepage ? row.homepage.value : null,
        languages: row.languages ? row.languages.value.split('||') : [],
        distributions: row.distributions
          ? row.distributions.value.split('||').filter(Boolean).map(str => {
              const [url, format] = str.split('|');
              return { url, format };
            })
          : [],
        dataThemes: row.dataThemes ? row.dataThemes.value.split('||') : []
      };
    });
    stream.on('end', () => {
      if (found) {
        res.json(found);
      } else {
        res.status(404).json({ error: 'Ontology not found' });
      }
    });
    stream.on('error', err => {
      console.error('SPARQL error:', err);
      res.status(500).json({ error: 'SPARQL query failed', details: err.message });
    });
  } catch (err) {
    console.error('SPARQL error:', err);
    res.status(500).json({ error: 'SPARQL query failed', details: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Backend server running on http://localhost:${PORT}`);
});