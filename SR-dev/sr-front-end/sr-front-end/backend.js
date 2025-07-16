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
    SELECT ?title ?description ?publisher ?lovRank
    FROM <http://semic.registry.eu>
    WHERE {
      ?standard a dct:Standard .
      ?standard dct:title ?title .
      ?standard dct:description ?description .
      ?standard dct:publisher ?publisher .
      ?standard <http://example.org/LOVRank> ?lovRank .
      FILTER (lang(?title) = "en")
      FILTER (lang(?description) = "en")
      FILTER(CONTAINS(LCASE(?title), LCASE("${query}")) || 
             CONTAINS(LCASE(?description), LCASE("${query}")))
    }
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
        ranking: row.lovRank.value
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

app.listen(PORT, () => {
  console.log(`Backend server running on http://localhost:${PORT}`);
}); 