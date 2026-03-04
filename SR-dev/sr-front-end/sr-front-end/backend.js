const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');

const VIRTUOSO_ENDPOINT = 'https://health.semic.eu/virtuoso/sparql';
const app = express();
const PORT = process.env.PORT || 4000;
const BASE_PATH = '/semantic-registry';

let SparqlClient;

// Dynamic import for ES module
async function initializeSparqlClient() {
  const module = await import('sparql-http-client');
  SparqlClient = module.default;
}

// Trust proxy (required for reverse proxy)
app.set('trust proxy', true);

app.use(cors());
app.use(bodyParser.json());

// Redirect root to base path
app.get('/', (req, res) => {
  res.redirect(301, BASE_PATH + '/');
});

// Health check endpoint (keep at root for load balancers)
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.use((req, res, next) => {
  // Skip if it's already a semantic-registry path or health check
  if (req.path.startsWith(BASE_PATH) || req.path === '/health') {
    return next();
  }
  
  // If it's an API request without the base path, redirect
  if (req.path.startsWith('/api/')) {
    return res.redirect(301, BASE_PATH + req.path);
  }
  
  // If it's a static file request, redirect
  if (req.path.match(/\.(js|css|png|jpg|jpeg|gif|ico|svg)$/)) {
    return res.redirect(301, BASE_PATH + req.path);
  }
  
  // For any other path, redirect to semantic-registry
  if (req.path !== '/') {
    return res.redirect(301, BASE_PATH + req.path);
  }
  
  next();
});

// API routes
app.post(BASE_PATH + '/api/search', async (req, res) => {
  if (!SparqlClient) {
    return res.status(500).json({ error: 'SPARQL client not initialized' });
  }

  const { query, theme, publisher } = req.body;

  if (!query || typeof query !== 'string') {
    return res.status(400).json({ error: 'Missing or invalid search query' });
  }

  // Check if query is a URI
  const isUri = query.startsWith('http://') || query.startsWith('https://');

  // Add theme filter dynamically if provided
  const themeFilter = theme
    ? `FILTER(?dataTheme = <${theme}>)`
    : '';

  // Add publisher filter dynamically if provided
  const publisherFilter = publisher
    ? `FILTER(?publisher = <${publisher}>)`
    : '';

  const sparqlQuery = `
    PREFIX dct: <http://purl.org/dc/terms/>
    PREFIX dc: <http://purl.org/dc/terms/>
    PREFIX adms: <http://www.w3.org/ns/adms#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    SELECT ?standard ?title ?description ?lovRank
      (GROUP_CONCAT(DISTINCT ?publisher; separator="|") AS ?publishers)
      (GROUP_CONCAT(DISTINCT CONCAT(STR(?requiringAsset), "|", COALESCE(?requiringTitle, ""), "|", COALESCE(?requiringPublisherName, STR(?requiringPublisher)), "|", COALESCE(STR(?requiringLocation), "")); SEPARATOR="||") AS ?requiringStandards)
      (GROUP_CONCAT(DISTINCT ?requiringPublisherName; SEPARATOR="||") AS ?requiringPublisherNames)
      (GROUP_CONCAT(DISTINCT STR(?requiringLocation); SEPARATOR="||") AS ?requiringLocations)
    WHERE {
      GRAPH <http://semic.registry.eu> {
        ?standard a adms:Asset .
        ?standard dct:title ?title .
        ?standard dct:description ?description .
        ?standard <http://data.europa.eu/m8g/lovRank> ?lovRank .
        ?standard dct:creator ?publisherNode .
        ?publisherNode foaf:name ?publisher .

        OPTIONAL {
          ?requiringAsset dc:requires ?standard .
          ?requiringAsset dc:title ?requiringTitle .
          ?requiringAsset dc:publisher ?requiringPublisher .
          OPTIONAL {
            ?requiringPublisher a foaf:Agent ;
                              foaf:name ?requiringPublisherName .
            FILTER(lang(?requiringPublisherName) = "en")
          }
          OPTIONAL {
            ?requiringAsset dc:creator ?requiringAgent .
            ?requiringAgent a foaf:Agent ;
                            dc:spatial ?requiringLocation .
            ?requiringLocation a dc:Location .
          }
          FILTER(lang(?requiringTitle) = "en")
        }

        FILTER(LANG(?title) = "en" || LANG(?title) = "")
        FILTER(LANG(?description) = "en" || LANG(?description) = "")
        FILTER(LANG(?publisher) = "en" || LANG(?publisher) = "")
        
        ${isUri
          ? `FILTER(?standard = <${query}>)`
          : (query && query !== '*'
              ? `FILTER(
            CONTAINS(LCASE(?title), LCASE("${query}")) ||
            CONTAINS(LCASE(?description), LCASE("${query}"))
          )`
              : '')
        }
        ${themeFilter}
        ${publisherFilter}
      }
    }
    GROUP BY ?standard ?title ?description ?lovRank
    ORDER BY DESC(?lovRank)
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
        publishers: row.publishers ? row.publishers.value.split('|') : [],
        ranking: row.lovRank.value,
        mainClasses: row.mainClasses ? row.mainClasses.value.split('||') : [],
        reusedOntologies: row.reusedOntologies
          ? row.reusedOntologies.value.split('||').filter(Boolean).map(str => {
              const [uri, title] = str.split('|');
              return { uri, title };
            })
          : [],
        requiringStandards: row.requiringStandards
          ? row.requiringStandards.value.split('||').filter(Boolean).map(str => {
              const [uri, title, publisher, location] = str.split('|');
              return { uri, title, publisher, location };
            })
          : [],
        requiringPublisherNames: row.requiringPublisherNames ? row.requiringPublisherNames.value.split('||').filter(Boolean) : [],
        requiringLocations: (() => {
          const locations = row.requiringLocations ? row.requiringLocations.value.split('||').filter(Boolean) : [];
          return locations;
        })(),
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

app.post(BASE_PATH + '/api/ontology', async (req, res) => {
  if (!SparqlClient) {
    return res.status(500).json({ error: 'SPARQL client not initialized' });
  }

  const { slug } = req.body;
  if (!slug || typeof slug !== 'string') {
    return res.status(400).json({ error: 'Missing or invalid slug' });
  }

  // Check if slug is actually a URI
  const isUri = slug.startsWith('http://') || slug.startsWith('https://');

  const sparqlQuery = `
    PREFIX dc: <http://purl.org/dc/terms/>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX adms: <http://www.w3.org/ns/adms#>

    SELECT ?title ?description ?lovRank
      (GROUP_CONCAT(DISTINCT COALESCE(?publisherName, STR(?publisher)); SEPARATOR="||") AS ?publishers)
      (GROUP_CONCAT(DISTINCT ?classLabel; SEPARATOR="||") AS ?mainClasses)
      (GROUP_CONCAT(DISTINCT CONCAT(STR(?reused), "|", COALESCE(?reusedTitle, "")); SEPARATOR="||") AS ?reusedOntologies)
      (GROUP_CONCAT(DISTINCT CONCAT(STR(?requiringAsset), "|", COALESCE(?requiringTitle, ""), "|", COALESCE(?requiringPublisherName, STR(?requiringPublisher)), "|", COALESCE(STR(?requiringLocation), "")); SEPARATOR="||") AS ?requiringStandards)
      (GROUP_CONCAT(DISTINCT ?requiringPublisherName; SEPARATOR="||") AS ?requiringPublisherNames)
      (GROUP_CONCAT(DISTINCT STR(?requiringLocation); SEPARATOR="||") AS ?requiringLocations)
      (GROUP_CONCAT(DISTINCT ?keyword; SEPARATOR="||") AS ?keywords)
      ?created ?homepage
      (GROUP_CONCAT(DISTINCT ?language; SEPARATOR="||") AS ?languages)
      (GROUP_CONCAT(DISTINCT CONCAT(STR(?downloadURL), "|", COALESCE(STR(?format), "")); SEPARATOR="||") AS ?distributions)
      (GROUP_CONCAT(DISTINCT COALESCE(?dataTheme, ?dataThemeGenerated); SEPARATOR="||") AS ?dataThemes)
    WHERE {
      GRAPH <http://semic.registry.eu> {
        ?asset a adms:Asset .
        ?asset dc:title ?title .
        ?asset dc:description ?description .
        ?asset dc:publisher ?publisher .
        OPTIONAL {
          ?publisher a foaf:Agent ;
                    foaf:name ?publisherName .
          FILTER(lang(?publisherName) = "en")
        }
        OPTIONAL {
          ?class a rdfs:Class ;
                rdfs:isDefinedBy ?distribution ;
                rdfs:label ?classLabel .
          ?asset dcat:distribution ?distribution .
          ?distribution a adms:AssetDistribution .
          FILTER(lang(?classLabel) = "en")
        }
        OPTIONAL {
          ?asset dc:requires ?reused .
          OPTIONAL { ?reused dc:title ?reusedTitle . FILTER(lang(?reusedTitle) = "en") }
        }
        OPTIONAL {
          ?requiringAsset dc:requires ?asset .
          ?requiringAsset dc:title ?requiringTitle .
          ?requiringAsset dc:publisher ?requiringPublisher .
          OPTIONAL {
            ?requiringPublisher a foaf:Agent ;
                              foaf:name ?requiringPublisherName .
            FILTER(lang(?requiringPublisherName) = "en")
          }
          OPTIONAL {
            ?requiringAsset dc:creator ?requiringAgent .
            ?requiringAgent a foaf:Agent ;
                          dc:spatial ?requiringLocation .
            ?requiringLocation a dc:Location .
          }
          FILTER(lang(?requiringTitle) = "en")
        }
        OPTIONAL { ?asset dcat:keyword ?keyword }
        OPTIONAL { ?asset dc:created ?created }
        OPTIONAL { ?asset foaf:homepage ?homepage }
        OPTIONAL { ?asset dc:language ?language }
        OPTIONAL {
          ?asset dcat:distribution ?distribution .
          ?distribution a adms:AssetDistribution ;
                      dcat:downloadURL ?downloadURL .
          OPTIONAL { ?distribution dc:format ?format }
        }
        OPTIONAL { ?asset dcat:theme ?dataTheme }
        ?asset <http://example.org/LOVRank> ?lovRank .
        FILTER (lang(?title) = "en")
        FILTER (lang(?description) = "en")
        ${isUri ?
          `FILTER(?asset = <${slug}>)` :
          `FILTER(REPLACE(LCASE(?title), "[^a-z0-9]+", "-", "g") = "${slug}")`
        }
      }
      
      OPTIONAL { 
        GRAPH <http://semic.registry2.eu> {
          ?asset dcat:theme ?dataThemeGenerated 
        }
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
        requiringStandards: row.requiringStandards
          ? row.requiringStandards.value.split('||').filter(Boolean).map(str => {
              const [uri, title, publisher, location] = str.split('|');
              return { uri, title, publisher, location };
            })
          : [],
        requiringPublisherNames: row.requiringPublisherNames ? row.requiringPublisherNames.value.split('||').filter(Boolean) : [],
        requiringLocations: (() => {
          const locations = row.requiringLocations ? row.requiringLocations.value.split('||').filter(Boolean) : [];
          return locations;
        })(),
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

// Serve static files from React build at the base path
app.use(BASE_PATH, express.static(path.join(__dirname, 'public')));

// Proxy routes (if needed)
app.use(BASE_PATH + '/proxy/*', createProxyMiddleware({
  target: 'https://health.semic.eu',
  changeOrigin: true,
  pathRewrite: {
    [`^${BASE_PATH}/proxy`]: ''
  }
}));

// Catch-all handler: send back React's index.html file for client-side routing
app.get(BASE_PATH + '*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Fallback for any other routes - redirect to base path
app.get('*', (req, res) => {
  res.redirect(BASE_PATH + '/');
});

// Initialize and start server
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

// Fallback handler for any unmatched routes
app.get('*', (req, res) => {
  // If the request doesn't start with BASE_PATH, redirect
  if (!req.path.startsWith(BASE_PATH)) {
    return res.redirect(301, BASE_PATH + '/');
  }
  
  // Otherwise, serve the React app
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

startServer();