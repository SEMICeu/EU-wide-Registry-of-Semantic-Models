import React, { useState } from 'react';
import './App.css';

function App() {
  const [search, setSearch] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleKeyDown = async (e) => {
    if (e.key === 'Enter') {
      setSubmittedQuery(search);
      setLoading(true);
      setError(null);
      setResults([]);
      try {
        const response = await fetch('http://localhost:4000/api/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: search })
        });
        if (!response.ok) {
          throw new Error('Failed to fetch results');
        }
        const data = await response.json();
        setResults(data);
      } catch (err) {
        setError(err.message || 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <div className="app-container">
      <header>
        <h1>The Semantic Registry</h1>
        <p>Search for semantic ontologies</p>
      </header>
      <div className="search-bar">
        <input
          type="text"
          placeholder="Search ontologies..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={handleKeyDown}
        />
      </div>
      {loading && <p className="loading">Loading...</p>}
      {error && <p className="error">{error}</p>}
      {submittedQuery && !loading && !error && (
        <div className="results">
          {results.length === 0 ? (
            <p className="no-results">No ontologies found.</p>
          ) : (
            results.map((onto, idx) => (
              <div className="ontology-card" key={idx}>
                <h2>{onto.title}</h2>
                <p className="description">{onto.description}</p>
                <div className="meta">
                  <span className="publisher">Publisher: {onto.publisher}</span>
                  <span className="ranking">Ranking: {onto.ranking}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default App; 