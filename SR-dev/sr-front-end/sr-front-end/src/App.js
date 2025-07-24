import React, { useState, useEffect } from 'react';
import './App.css';
import { BrowserRouter as Router, Routes, Route, useNavigate, useParams, useLocation } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { getLanguageLabel } from './languageMapping';
import { getFormatLabel } from './formatMapping';
import { allDataThemes, getDataThemeLabel } from './dataThemeMapping';
import { allPublishers, getPublisherLabel } from './publisherMapping';

// Helper to map ranking (0-1) to stars and meaning
function getRankingDisplay(ranking) {
  if (ranking >= 0.85) return { stars: "⭐⭐⭐⭐⭐", label: "Highly Interoperable" };
  if (ranking >= 0.65) return { stars: "⭐⭐⭐⭐", label: "Widely Reused" };
  if (ranking >= 0.35) return { stars: "⭐⭐⭐", label: "Commonly Reused" };
  if (ranking >= 0.1) return { stars: "⭐⭐", label: "Occasionally Reused" };
  return { stars: "⭐", label: "Rarely Reused" };
}

function slugifyTitle(titleOrUri) {
  return (titleOrUri || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

function About() {
  const ratings = [
    { stars: '⭐⭐⭐⭐⭐', title: 'Highly Interoperable', description: 'This ontology is among the most reused within the graph and adoption of this ontology or its elements will ensure the highest level of interoperability.' },
    { stars: '⭐⭐⭐⭐', title: 'Widely Reused', description: 'This ontology is widely reused within the graph and adoption of this ontology or its elements will ensure a strong level of interoperability.' },
    { stars: '⭐⭐⭐', title: 'Commonly Reused', description: 'This ontology is commonly reused within the graph and adoption of this ontology or its elements will ensure a good level of interoperability.' },
    { stars: '⭐⭐', title: 'Occasionally Reused', description: 'This ontology is occasionally reused within the graph and adoption of this ontology or its elements will ensure a modest level of interoperability.' },
    { stars: '⭐', title: 'Rarely Reused', description: 'This ontology is rarely reused within the graph and adoption of this ontology or its elements will ensure the lowest level of interoperability.' },
  ];
  return (
    <div className="about-container">
      <h1 className="about-heading">About the Ranking System</h1>
      <p className="about-paragraph">
        Our ranking system evaluates semantic ontologies based on their reuse within the graph of the Semantic Registry.
      </p>
      <p className="about-paragraph">
        It does so by calculating a score for each ontology by counting the number of times it is reused by other ontologies. To make the interpretation of these scores more intuitive each score is assigned a number of starts between 1 and 5.
      </p>
      <p className="about-paragraph">
        For example, if elements of an ontology are reused in half of all the ontologies in the graph it will receive a score of 0.5.
      </p>
      <h2 className="about-subheading">Five-Star Rating Explained</h2>

      <div className="rating-list">
        {ratings.map(({ stars, title, description }) => (
          <div className="rating-row" key={title}>
            <button className="rating-button" type="button" aria-label={`${title} rating`}>
              <span className="rating-stars">{stars}</span>
              <span className="rating-title">{title}</span>
            </button>
            <p className="rating-description">{description}</p>
          </div>
        ))}
      </div>
    </div>
  );
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
          <span className="ontology-detail-publisher-label">Publisher:</span>
          <div className="publisher-list">
            {ontology.publishers?.map((publisher, index) => (
              <span key={index} className="publisher-tag">
                {publisher}
              </span>
            ))}
          </div>
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
          {ontology.distributions && ontology.distributions.length > 0 ? (
            <table className="ontology-detail-table">
              <thead>
                <tr>
                  <th>Link to the distribution</th>
                  <th>Format</th>
                </tr>
              </thead>
              <tbody>
                {ontology.distributions.map((dist, idx) => (
                  <tr key={idx}>
                    <td>
                      <a
                        href={dist.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {`Distribution ${idx + 1}`}
                      </a>
                    </td>
                    <td>
                      {getFormatLabel(dist.format)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <span style={{ color: '#7eb6ff' }}>No distributions listed.</span>
          )}
        </div>
        <div className="ontology-detail-section">
          <h3>Data Themes</h3>
          {ontology.dataThemes && ontology.dataThemes.length > 0 ? (
            <ul className="ontology-detail-keywords">
              {ontology.dataThemes.map((theme, idx) => (
                <li key={idx}>{getDataThemeLabel(theme)}</li>
              ))}
            </ul>
          ) : (
            <span style={{ color: '#7eb6ff' }}>No data themes listed.</span>
          )}
        </div>
        <div className="ontology-detail-section">
          <h3>Keywords</h3>
          {ontology.keywords && ontology.keywords.length > 0 ? (
            <ul className="ontology-detail-keywords">
              {ontology.keywords.map((kw, idx) => (
                <li key={idx}>{kw}</li>
              ))}
            </ul>
          ) : (
            <span style={{ color: '#7eb6ff' }}>No keywords listed.</span>
          )}
        </div>
      </div>
      <aside className="ontology-detail-meta">
        <div className="ontology-detail-meta-box">
            {(() => {
              const { stars, label } = getRankingDisplay(ontology.ranking);
              return (
                <div className="ontology-card-ranking">
                  <div className="stars">{stars}</div>
                  <div className="ranking-label">{label}</div>
                </div>
              );
            })()}
        </div>
        <div className="ontology-detail-meta-box">
          <div><b>Created:</b> {ontology.created ? new Date(ontology.created).toLocaleDateString() : <span style={{color:'#7eb6ff'}}>Unknown</span>}</div>
          <div><b>Landing Page:</b> {ontology.homepage ? <a href={ontology.homepage} target="_blank" rel="noopener noreferrer">{ontology.homepage}</a> : <span style={{color:'#7eb6ff'}}>None</span>}</div>
          <div>
          <b>Languages:</b>{" "}
          {ontology.languages && ontology.languages.length > 0 ? (
            ontology.languages.map((lang, idx) => (
              <span key={idx}>
                {getLanguageLabel(lang)}
                {idx < ontology.languages.length - 1 ? ', ' : ''}
              </span>
            ))
          ) : (
            <span style={{ color: '#7eb6ff' }}>Unknown</span>
          )}
        </div>
        </div>
        {ontology.reusedOntologies && ontology.reusedOntologies.length > 0 && (
          <div className="ontology-detail-reuses-box">
            <div className="ontology-detail-reuses-title">This ontology reuses:</div>
            <ul className="ontology-detail-reuses-list">
              {ontology.reusedOntologies.map((onto, idx) => {
                return (
                  <li key={idx}>
                    <button style={{ background: 'none', border: 'none', color: '#7eb6ff', textDecoration: 'underline', cursor: 'pointer', padding: 0 }}
                      onClick={() => navigate(`/ontology/${encodeURIComponent(onto.uri)}`)}>
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
  const [selectedTheme, setSelectedTheme] = useState('');
  const [selectedPublisher, setSelectedPublisher] = useState('');
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
          body: JSON.stringify({ 
            query: search,
            theme: selectedTheme || null,
            publisher: selectedPublisher || null
          })
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
  const handleFilterChange = async (newTheme = selectedTheme, newPublisher = selectedPublisher) => {
    if (!search.trim()) return; // Don't search if search box is empty
    
    setSubmittedQuery(search);
    setLoading(true);
    setError(null);
    setResults([]);
    try {
      const response = await fetch('http://localhost:4000/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: search,
          theme: newTheme || null,
          publisher: newPublisher || null
        })
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
  };
  return (
    <div className="main-content">
      <div className="intro-section">
        <h2>Welcome to the Semantic Registry</h2>
        <p>
          The Semantic Registry contains semantic models from well known publishers, Member States, European Agencies and more. It uses ranking metrics to recommend semantic models that are the most commonly used and interconnected with other models, allowing you to make the best decision for your use case!
        </p>
      </div>
      <div className="search-filter-container">
        <div className="search-bar">
          <input
            type="text"
            placeholder="Search ontologies..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>
        <div className="filter-bar">
          {/* Data Theme Filter */}
          <label htmlFor="theme-select" className="sr-only">
            Filter by data theme
          </label>
          <select
            id="theme-select"
            value={selectedTheme}
            onChange={e => {
              const newTheme = e.target.value;
              setSelectedTheme(newTheme);
              if (search.trim()) {
                handleFilterChange(newTheme, selectedPublisher);
              }
            }}
          >
            <option value="">All Themes</option>
            {allDataThemes.map(theme => (
              <option key={theme.iri} value={theme.iri}>
                {theme.label}
              </option>
            ))}
          </select>

          {/* Publisher Filter */}
          <label htmlFor="publisher-select" className="sr-only">
            Filter by publisher
          </label>
          <select
          id="publisher-select"
          value={selectedPublisher}
          onChange={e => {
            const newPublisher = e.target.value;
            setSelectedPublisher(newPublisher);
            if (search.trim()) {
              handleFilterChange(selectedTheme, newPublisher);
            }
          }}
          >
            <option value="">All Publishers</option>
            {allPublishers.map(publisher => (
              <option key={publisher.iri} value={publisher.iri}>
                {publisher.label}
              </option>
            ))}
          </select>
        </div>
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
                    <span className="ontology-card-ranking">{(() => {
                      const { stars, label } = getRankingDisplay(onto.ranking);
                      return (
                        <div className="ontology-card-ranking">
                          <div className="stars">{stars}</div>
                          <div className="ranking-label">{label}</div>
                        </div>
                      );
                    })()}
                    </span>
                  </div>
                  <div className="ontology-card-meta">
                    <span className="publisher-label">Publisher:</span>
                    <div className="publisher-list">
                      {onto.publishers?.map((publisher, index) => (
                        <span key={index} className="publisher-tag">
                          {publisher}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="ontology-card-description">{onto.description}</div>
                  {onto.dataThemes && onto.dataThemes.length > 0 && (
                    <div className="ontology-card-themes">
                      <span className="ontology-card-themes-title">Data Themes:</span>
                      {onto.dataThemes.map((theme, i) => (
                        <span className="ontology-card-theme-tag" key={i}>
                          {getDataThemeLabel(theme)}
                        </span>
                      ))}
                    </div>
                  )}
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
          <div className="logo-title-container">
            <img
              src="/semic-logo.png"
              alt="Semantic Registry Logo"
              className="navbar-logo"
            />
            <h1 onClick={handleTitleClick}>The Semantic Registry</h1>
          </div>

          {/* Replace paragraph with button */}
          <Link to="/about">
            <button className="about-button">Click here to learn more about the ranking.</button>
          </Link>
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
        <Route path="/about" element={<About />} />
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