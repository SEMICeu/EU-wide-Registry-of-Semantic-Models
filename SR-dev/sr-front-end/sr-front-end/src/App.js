import React, { useState, useEffect } from 'react';
import './App.css';
import { BrowserRouter as Router, Routes, Route, useNavigate, useParams, useLocation } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { getLanguageLabel } from './languageMapping';
import { getFormatLabel } from './formatMapping';
import { allDataThemes, getDataThemeLabel } from './dataThemeMapping';
import { allPublishers, getPublisherLabel } from './publisherMapping';
import 'flag-icons/css/flag-icons.min.css';
import { getCountryLabel, getCountryCode } from './countryMapping';

// Ranking-based UI removed

function slugifyTitle(titleOrUri) {
  return titleOrUri
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

// Helper function to extract unique publishers and countries from requiring standards
function extractUniquePublishersAndCountries(requiringStandards) {
  if (!requiringStandards || requiringStandards.length === 0) {
    return [];
  }

  const publisherMap = new Map();

  requiringStandards.forEach(standard => {
    const publisher = standard.publisher;
    const location = standard.location;
    
    if (publisher && publisher.trim() !== '') {
      // Clean up the publisher name (remove any URI prefixes if present)
      const cleanPublisher = publisher.replace(/^https?:\/\/[^\/]+\//, '').replace(/^http:\/\/[^\/]+\//, '');
      
      if (!publisherMap.has(cleanPublisher)) {
        publisherMap.set(cleanPublisher, {
          publisher: cleanPublisher,
          countries: new Set(),
          count: 0
        });
      }
      
      const entry = publisherMap.get(cleanPublisher);
      entry.count++;
      
      if (location && location.trim() !== '') {
        // Clean up the location name (remove any URI prefixes if present)
        const cleanLocation = location.replace(/^https?:\/\/[^\/]+\//, '').replace(/^http:\/\/[^\/]+\//, '');
        entry.countries.add(cleanLocation);
      }
    }
  });

  return Array.from(publisherMap.values()).map(entry => ({
    publisher: entry.publisher,
    countries: Array.from(entry.countries),
    count: entry.count
  }));
}

// New function to extract unique publishers from requiring standards
function getUniquePublishersFromRequiringStandards(requiringStandards) {
  if (!requiringStandards || requiringStandards.length === 0) {
    return [];
  }

  console.log('Raw requiring standards data:', requiringStandards);

  const uniquePublishers = new Set();
  
  requiringStandards.forEach((standard, index) => {
    console.log(`Standard ${index}:`, standard);
    console.log(`Standard ${index} publisher field:`, standard.publisher);
    
    if (standard.publisher && standard.publisher.trim() !== '') {
      // Clean up the publisher name (remove any URI prefixes if present)
      const cleanPublisher = standard.publisher.replace(/^https?:\/\/[^\/]+\//, '').replace(/^http:\/\/[^\/]+\//, '');
      console.log(`Standard ${index} clean publisher:`, cleanPublisher);
      uniquePublishers.add(cleanPublisher);
    }
  });

  const result = Array.from(uniquePublishers);
  console.log('Final unique publishers:', result);
  return result;
}

// Simple function to get unique publisher names from the dedicated field
function getUniqueRequiringPublisherNames(requiringPublisherNames) {
  if (!requiringPublisherNames || requiringPublisherNames.length === 0) {
    return [];
  }

  console.log('Raw requiring publisher names:', requiringPublisherNames);
  
  // Filter out empty strings and get unique values
  const uniquePublishers = [...new Set(requiringPublisherNames.filter(name => name && name.trim() !== ''))];
  
  console.log('Final unique requiring publisher names:', uniquePublishers);
  return uniquePublishers;
}

// Simple function to get unique requiring locations (countries) from the dedicated field
function getUniqueRequiringLocations(requiringLocations) {
  if (!requiringLocations || requiringLocations.length === 0) {
    console.log('No requiring locations data available');
    return [];
  }

  console.log('Raw requiring locations:', requiringLocations);
  console.log('Requiring locations length:', requiringLocations.length);
  
  // Filter out empty strings and get unique values, keep full URIs for mapping
  const uniqueLocations = [...new Set(requiringLocations
    .filter(location => location && location.trim() !== '')
  )];
  
  console.log('Filtered locations:', requiringLocations.filter(location => location && location.trim() !== ''));
  console.log('Final unique requiring locations:', uniqueLocations);
  return uniqueLocations;
}

// Helper function to truncate text to 50 words
function truncateToWords(text, maxWords = 50) {
  if (!text) return '';
  const words = text.split(' ');
  if (words.length <= maxWords) return text;
  return words.slice(0, maxWords).join(' ') + '...';
}

// About page removed

function OntologyDetail({ ontologies }) {
  const { slug } = useParams();
  const [fetchedOntology, setFetchedOntology] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedSections, setExpandedSections] = useState({
    reuses: true,
    reusedBy: true
  });
  const ontologyIdx = ontologies.findIndex(o => slugifyTitle(o.title) === slug);
  const ontology = ontologyIdx !== -1 ? ontologies[ontologyIdx] : fetchedOntology;
  const navigate = useNavigate();

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

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
        <div className="ontology-detail-section">
          <h3>Publisher</h3>
          {ontology.publishers && ontology.publishers.length > 0 ? (
            <ul className="ontology-detail-keywords">
              {ontology.publishers.map((publisher, idx) => (
                <li key={idx}>{publisher}</li>
              ))}
            </ul>
          ) : (
            <span style={{ color: '#7eb6ff' }}>No publisher listed.</span>
          )}
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
        
        {ontology.reusedOntologies && ontology.reusedOntologies.length > 0 && (
          <div className="ontology-detail-section">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                 onClick={() => toggleSection('reuses')}>
              <h3>This ontology reuses ({ontology.reusedOntologies.length})</h3>
              <span style={{ fontSize: '1.2rem', color: '#075CA8' }}>
                {expandedSections.reuses ? '−' : '+'}
              </span>
            </div>
            {expandedSections.reuses && (
              <ul className="ontology-detail-keywords">
                {ontology.reusedOntologies.map((onto, idx) => {
                  return (
                    <li key={idx}>
                      <button style={{ background: 'none', border: 'none', color: '#075CA8', textDecoration: 'underline', cursor: 'pointer', padding: 0 }}
                        onClick={() => navigate(`/ontology/${encodeURIComponent(onto.uri)}`)}>
                        {onto.title ? onto.title : onto.uri}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
        
        {ontology.requiringStandards && ontology.requiringStandards.length > 0 && (
          <div className="ontology-detail-section">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                 onClick={() => toggleSection('reusedBy')}>
              <h3>This ontology is reused by ({ontology.requiringStandards.length})</h3>
              <span style={{ fontSize: '1.2rem', color: '#075CA8' }}>
                {expandedSections.reusedBy ? '−' : '+'}
              </span>
            </div>
            {expandedSections.reusedBy && (
              <ul className="ontology-detail-keywords">
                {ontology.requiringStandards.map((onto, idx) => {
                  return (
                    <li key={idx}>
                      <button style={{ background: 'none', border: 'none', color: '#075CA8', textDecoration: 'underline', cursor: 'pointer', padding: 0 }}
                        onClick={() => navigate(`/ontology/${encodeURIComponent(onto.uri)}`)}>
                        {onto.title ? onto.title : onto.uri}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </div>
      <aside className="ontology-detail-meta">
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
        <div className="ontology-detail-meta-box">
            {ontology.requiringStandards && ontology.requiringStandards.length > 0 && (
              <div style={{ marginTop: '16px' }}>
                <div style={{ fontWeight: 'bold', marginBottom: '8px', color: '#0E1F2F' }}>Reused by</div>
                <div style={{ marginBottom: '12px' }}>
                  <div style={{ fontWeight: '600', marginBottom: '4px', color: '#075CA8', fontSize: '0.95rem' }}>Country</div>
                  {(() => {
                    const uniqueLocations = getUniqueRequiringLocations(ontology.requiringLocations);
                    return uniqueLocations.length > 0 ? (
                      <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
                        {uniqueLocations.map((location, idx) => {
                          const code = getCountryCode(location);
                          const name = getCountryLabel(location);
                          return (
                            <li key={idx} style={{ 
                              background: '#e3eafc', 
                              color: '#0E1F2F', 
                              borderRadius: '6px', 
                              padding: '5px 14px', 
                              fontSize: '1rem',
                              marginBottom: '4px',
                              display: 'inline-block',
                              marginRight: '6px'
                            }}>
                              {code && <span className={`fi fi-${code}`} style={{marginRight: '8px'}}></span>}
                              {name}
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <span style={{ color: '#7eb6ff' }}>No country information available.</span>
                    );
                  })()}
                </div>
                <div>
                  <div style={{ fontWeight: '600', marginBottom: '4px', color: '#075CA8', fontSize: '0.95rem' }}>Publisher</div>
                  {(() => {
                    const uniquePublishers = getUniqueRequiringPublisherNames(ontology.requiringPublisherNames);
                    return uniquePublishers.length > 0 ? (
                      <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
                        {uniquePublishers.map((publisher, idx) => (
                          <li key={idx} style={{ 
                            background: '#e3eafc', 
                            color: '#0E1F2F', 
                            borderRadius: '6px', 
                            padding: '5px 14px', 
                            fontSize: '1rem',
                            marginBottom: '4px',
                            display: 'inline-block',
                            marginRight: '6px'
                          }}>{publisher}</li>
                        ))}
                      </ul>
                    ) : (
                      <span style={{ color: '#7eb6ff' }}>No publisher information available.</span>
                    );
                  })()}
                </div>
              </div>
            )}
        </div>
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
        <h2>Welcome to the SEMIC Semantic Registry</h2>
        <p>
          The Semantic Registry contains technical, implementation and relationship information, that are intended to promote the increasing convergence to semantic interoperability. The information can be used in support to the semantic modelling task as evidence to guide the selection of the semantic elements that will overall increase the semantic interoperability of the adopters.
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
            results.map((onto, idx) => (
                <div
                  className="ontology-card"
                  key={idx}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/ontology/${slugifyTitle(onto.title)}`)}
                >
                  <div className="ontology-card-header">
                    <span className="ontology-card-title">{onto.title}</span>
                  </div>
                  {onto.publishers && onto.publishers.length > 0 && (
                    <div className="ontology-card-main-classes">
                      <span className="ontology-card-main-classes-title">Publisher</span>
                      {onto.publishers.slice(0, 3).map((publisher, i) => (
                        <span className="ontology-card-main-class-tag" key={i}>
                          {publisher}
                        </span>
                      ))}
                    </div>
                  )}
                  {onto.description && (
                    <div className="ontology-card-description">
                      {truncateToWords(onto.description)}
                    </div>
                  )}
                  {onto.requiringStandards && onto.requiringStandards.length > 0 && (
                    <div className="ontology-card-main-classes">
                      <div className="ontology-card-subsection-title">Reused by</div>
                      <div className="ontology-card-subsection">
                        <span className="ontology-card-subsection-title-grey">Country</span>
                        {(() => {
                          const uniqueLocations = getUniqueRequiringLocations(onto.requiringLocations);
                          return uniqueLocations.slice(0, 3).map((location, i) => (
                            <span className="ontology-card-main-class-tag" key={i}>
                              <span className={`fi fi-${getCountryCode(location)}`}></span>{' '}{getCountryLabel(location)}
                            </span>
                          ));
                        })()}
                        {(() => {
                          const uniqueLocations = getUniqueRequiringLocations(onto.requiringLocations);
                          return uniqueLocations.length > 3 && (
                            <span className="ontology-card-main-class-tag">
                              +{uniqueLocations.length - 3} more
                            </span>
                          );
                        })()}
                      </div>
                      <div className="ontology-card-subsection">
                        <span className="ontology-card-subsection-title-grey">Publisher</span>
                        {(() => {
                          const uniquePublishers = getUniqueRequiringPublisherNames(onto.requiringPublisherNames);
                          return uniquePublishers.slice(0, 3).map((pub, i) => (
                            <span className="ontology-card-main-class-tag" key={i}>
                              {pub}
                            </span>
                          ));
                        })()}
                        {(() => {
                          const uniquePublishers = getUniqueRequiringPublisherNames(onto.requiringPublisherNames);
                          return uniquePublishers.length > 3 && (
                            <span className="ontology-card-main-class-tag">
                              +{uniquePublishers.length - 3} more
                            </span>
                          );
                        })()}
                      </div>
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
              src="/semic-logo-cropped.png"
              alt="Semantic Registry Logo"
              className="navbar-logo"
            />
            <h1 onClick={handleTitleClick}>The Semantic Registry</h1>
          </div>
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
        {/* About route removed */}
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