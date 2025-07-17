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
  const { query } = req.body;
  if (!query || typeof query !== 'string') {
    return res.status(400).json({ error: 'Missing or invalid search query' });
  }

  const sparqlQuery = `
    PREFIX dct: <http://purl.org/dc/terms/>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    SELECT ?title ?description ?publisher ?publisherName ?lovRank (GROUP_CONCAT(DISTINCT ?classLabel; SEPARATOR="||") AS ?mainClasses) (GROUP_CONCAT(DISTINCT CONCAT(STR(?reused), "|", COALESCE(?reusedTitle, "")); SEPARATOR="||") AS ?reusedOntologies) (GROUP_CONCAT(DISTINCT ?keyword; SEPARATOR="||") AS ?keywords) ?created ?homepage (GROUP_CONCAT(DISTINCT ?language; SEPARATOR="||") AS ?languages)
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
          FILTER(
            CONTAINS(LCASE(?title), LCASE("${query}")) ||
            CONTAINS(LCASE(?description), LCASE("${query}")) ||
            CONTAINS(LCASE(?classLabel), LCASE("${query}"))
          )
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
      ?standard <http://example.org/LOVRank> ?lovRank .
      FILTER (lang(?title) = "en")
      FILTER (lang(?description) = "en")
    }
    GROUP BY ?title ?description ?publisher ?publisherName ?lovRank ?created ?homepage
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
        publisher: row.publisher.value,
        publisherName: row.publisherName ? row.publisherName.value : row.publisher.value,
        ranking: row.lovRank.value,
        mainClasses: row.mainClasses ? row.mainClasses.value.split('||') : [],
        reusedOntologies: row.reusedOntologies ? row.reusedOntologies.value.split('||').filter(Boolean).map(str => {
          const [uri, title] = str.split('|');
          return { uri, title };
        }) : [],
        keywords: row.keywords ? row.keywords.value.split('||') : [],
        created: row.created ? row.created.value : null,
        homepage: row.homepage ? row.homepage.value : null,
        languages: row.languages ? row.languages.value.split('||') : []
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

  const sparqlQuery = `
    PREFIX dct: <http://purl.org/dc/terms/>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?title ?description ?publisher ?publisherName ?lovRank (GROUP_CONCAT(DISTINCT ?classLabel; SEPARATOR="||") AS ?mainClasses) (GROUP_CONCAT(DISTINCT CONCAT(STR(?reused), "|", COALESCE(?reusedTitle, "")); SEPARATOR="||") AS ?reusedOntologies) (GROUP_CONCAT(DISTINCT ?keyword; SEPARATOR="||") AS ?keywords) ?created ?homepage (GROUP_CONCAT(DISTINCT ?language; SEPARATOR="||") AS ?languages)
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
        ?class a <http://www.w3.org/2000/01/rdf-schema#Class> ;
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
      ?standard <http://example.org/LOVRank> ?lovRank .
      FILTER (lang(?title) = "en")
      FILTER (lang(?description) = "en")
      FILTER(REPLACE(LCASE(?title), "[^a-z0-9]+", "-", "g") = "${slug}")
    }
    GROUP BY ?title ?description ?publisher ?publisherName ?lovRank ?created ?homepage
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
        publisher: row.publisher.value,
        publisherName: row.publisherName ? row.publisherName.value : row.publisher.value,
        ranking: row.lovRank.value,
        mainClasses: row.mainClasses ? row.mainClasses.value.split('||') : [],
        reusedOntologies: row.reusedOntologies ? row.reusedOntologies.value.split('||').filter(Boolean).map(str => {
          const [uri, title] = str.split('|');
          return { uri, title };
        }) : [],
        keywords: row.keywords ? row.keywords.value.split('||') : [],
        created: row.created ? row.created.value : null,
        homepage: row.homepage ? row.homepage.value : null,
        languages: row.languages ? row.languages.value.split('||') : []
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