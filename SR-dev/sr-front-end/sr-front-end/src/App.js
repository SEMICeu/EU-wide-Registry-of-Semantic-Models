import React, { useState, useEffect } from 'react';
import './App.css';
import { BrowserRouter as Router, Routes, Route, useNavigate, useParams, useLocation } from 'react-router-dom';

function slugifyTitle(titleOrUri) {
  return (titleOrUri || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

function OntologyDetail({ ontologies }) {
  const { slug } = useParams();
  const [fetchedOntology, setFetchedOntology] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const ontologyIdx = ontologies.findIndex(o => slugifyTitle(o.title) === slug);
  const ontology = ontologyIdx !== -1 ? ontologies[ontologyIdx] : fetchedOntology;
  const navigate = useNavigate();

  useEffect(() => {
    if (ontologyIdx === -1) {
      setLoading(true);
      setError(null);
      fetch('http://localhost:4000/api/ontology', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug })
      })
        .then(res => {
          if (!res.ok) throw new Error('Ontology not found');
          return res.json();
        })
        .then(data => {
          setFetchedOntology(data);
          setLoading(false);
        })
        .catch(err => {
          setError(err.message);
          setLoading(false);
        });
    } else {
      setFetchedOntology(null);
      setLoading(false);
      setError(null);
    }
  }, [slug, ontologyIdx]);

  if (loading) return <div className="ontology-detail-bg"><div className="ontology-detail-card"><h2>Loading...</h2></div></div>;
  if (!ontology) return <div className="ontology-detail-bg"><div className="ontology-detail-card"><h2>Ontology not found</h2>{error && <div style={{color:'#ff6b6b'}}>{error}</div>}</div></div>;

  return (
    <div className="ontology-detail-layout">
      <div className="ontology-detail-main">
        <div className="ontology-detail-header">
          <h2>{ontology.title}</h2>
        </div>
        <div className="ontology-detail-publisher">
          <span className="ontology-detail-publisher-label">Publisher:</span> {ontology.publisherName || ontology.publisher}
        </div>
        <div className="ontology-detail-description">
          {ontology.description}
        </div>
        <div className="ontology-detail-section">
          <h3>Main Classes</h3>
          {ontology.mainClasses && ontology.mainClasses.length > 0 ? (
            <ul className="ontology-detail-keywords">
              {ontology.mainClasses.map((cls, idx) => (
                <li key={idx}>{cls}</li>
              ))}
            </ul>
          ) : (
            <span style={{ color: '#7eb6ff' }}>No main classes listed.</span>
          )}
        </div>
        <div className="ontology-detail-section">
          <h3>Distributions</h3>
          <table className="ontology-detail-table">
            <thead>
              <tr>
                <th>Link to the data</th>
                <th>Format</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>ontology</td>
                <td>HTML</td>
                <td>UNKNOWN</td>
                <td>Access</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="ontology-detail-section">
          <h3>Keywords</h3>
          <ul className="ontology-detail-keywords">
            <li>ontology</li>
            <li>example</li>
            <li>data</li>
          </ul>
        </div>
      </div>
      <aside className="ontology-detail-meta">
        <div className="ontology-detail-meta-box">
          <div><b>Ranking:</b> {ontology.ranking}</div>
          <div><b>Created:</b> 31.01.2025</div>
          <div><b>Landing Page:</b> <a href="#" target="_blank" rel="noopener noreferrer">example.com</a></div>
          <div><b>Languages:</b> Dutch</div>
        </div>
        {ontology.reusedOntologies && ontology.reusedOntologies.length > 0 && (
          <div className="ontology-detail-reuses-box">
            <div className="ontology-detail-reuses-title">This ontology reuses:</div>
            <ul className="ontology-detail-reuses-list">
              {ontology.reusedOntologies.map((onto, idx) => {
                const reusedIdx = ontologies.findIndex(o => o.publisher === onto.uri);
                const reusedSlug = onto.title ? slugifyTitle(onto.title) : slugifyTitle(onto.uri);
                return (
                  <li key={idx}>
                    <button style={{ background: 'none', border: 'none', color: '#7eb6ff', textDecoration: 'underline', cursor: 'pointer', padding: 0 }}
                      onClick={() => navigate(`/ontology/${reusedSlug}`)}>
                      {onto.title ? onto.title : onto.uri}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </aside>
    </div>
  );
}

function SearchPage({ search, setSearch, submittedQuery, setSubmittedQuery, results, setResults, loading, setLoading, error, setError }) {
  const navigate = useNavigate();
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
    <div className="main-content">
      <div className="intro-section">
        <h2>Welcome to the Semantic Registry</h2>
        <p>
          The Semantic Registry contains semantic models from well known publishers, Member States, European Agencies and more. It uses ranking metrics to recommend semantic models that are the most commonly used and interconnected with other models, making you more interoperable!
        </p>
      </div>
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
            [...results]
              .sort((a, b) => parseFloat(b.ranking) - parseFloat(a.ranking))
              .map((onto, idx) => (
                <div
                  className="ontology-card"
                  key={idx}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/ontology/${slugifyTitle(onto.title)}`)}
                >
                  <div className="ontology-card-header">
                    <span className="ontology-card-title">{onto.title}</span>
                    <span className="ontology-card-ranking">{onto.ranking}</span>
                  </div>
                  <div className="ontology-card-meta">
                    <span className="publisher">Publisher: {onto.publisherName || onto.publisher}</span>
                  </div>
                  <div className="ontology-card-description">{onto.description}</div>
                  {onto.mainClasses && onto.mainClasses.length > 0 && (
                    <div className="ontology-card-main-classes">
                      <span className="ontology-card-main-classes-title">Main classes:</span>
                      {onto.mainClasses.map((cls, i) => (
                        <span className="ontology-card-main-class-tag" key={i}>{cls}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))
          )}
        </div>
      )}
    </div>
  );
}

function App() {
  const [search, setSearch] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const navigate = useNavigate();

  const handleTitleClick = () => {
    setSearch('');
    setSubmittedQuery('');
    setResults([]);
    setError(null);
    setLoading(false);
    navigate('/');
  };

  return (
    <>
      <nav className="navbar">
        <div className="navbar-content">
          <h1 onClick={handleTitleClick}>The Semantic Registry</h1>
          <p>Search for semantic ontologies</p>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={
          <SearchPage
            search={search}
            setSearch={setSearch}
            submittedQuery={submittedQuery}
            setSubmittedQuery={setSubmittedQuery}
            results={results}
            setResults={setResults}
            loading={loading}
            setLoading={setLoading}
            error={error}
            setError={setError}
          />
        } />
        <Route path="/ontology/:slug" element={<OntologyDetail ontologies={results} />} />
      </Routes>
    </>
  );
}

export default function AppWithRouter() {
  return (
    <Router>
      <App />
    </Router>
  );
} 