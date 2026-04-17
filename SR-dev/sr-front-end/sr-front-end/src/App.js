import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import { BrowserRouter as Router, Routes, Route, useNavigate, useParams, useLocation, useSearchParams } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { getLanguageLabel } from './languageMapping';
import { getFormatLabel } from './formatMapping';
import { allDataThemes, getDataThemeLabel } from './dataThemeMapping';
import { allPublishers, getPublisherLabel } from './publisherMapping';
import 'flag-icons/css/flag-icons.min.css';
import { getCountryLabel, getCountryCode } from './countryMapping';

// Hardcoded base path for the app
const BASE_PATH = '/semantic-registry';
const API_BASE = process.env.REACT_APP_API_URL || BASE_PATH;

// Ranking-based UI removed

function slugifyTitle(titleOrUri) {
  return titleOrUri
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

// Get unique publisher names from the requiringPublisherNames field
function getUniqueRequiringPublisherNames(requiringPublisherNames) {
  if (!requiringPublisherNames || requiringPublisherNames.length === 0) return [];
  return [...new Set(requiringPublisherNames.filter(name => name && name.trim() !== ''))];
}

// Get unique requiring locations (country URIs) from the requiringLocations field
function getUniqueRequiringLocations(requiringLocations) {
  if (!requiringLocations || requiringLocations.length === 0) return [];
  return [...new Set(requiringLocations.filter(location => location && location.trim() !== ''))];
}

// Helper function to truncate publisher name to 30 characters
function truncatePublisher(name, maxChars = 30) {
  if (!name) return '';
  if (name.length <= maxChars) return name;
  return name.slice(0, maxChars) + '...';
}

// Helper function to truncate text to 50 words
function truncateToWords(text, maxWords = 50) {
  if (!text) return '';
  const words = text.split(' ');
  if (words.length <= maxWords) return text;
  return words.slice(0, maxWords).join(' ') + '...';
}

// Map of known RDF namespace URIs to their conventional prefixes
const KNOWN_PREFIXES = [
  ['http://www.w3.org/2002/07/owl#',                'owl'],
  ['http://www.w3.org/2000/01/rdf-schema#',         'rdfs'],
  ['http://www.w3.org/1999/02/22-rdf-syntax-ns#',   'rdf'],
  ['http://www.w3.org/ns/dcat#',                    'dcat'],
  ['http://purl.org/dc/terms/',                     'dct'],
  ['http://xmlns.com/foaf/0.1/',                    'foaf'],
  ['http://data.europa.eu/m8g/',                    'cv'],
  ['http://www.w3.org/ns/adms#',                    'adms'],
  ['http://schema.org/',                            'schema'],
  ['http://www.w3.org/2004/02/skos/core#',          'skos'],
  ['http://www.w3.org/ns/org#',                     'org'],
  ['http://www.w3.org/2006/time#',                  'time'],
  ['http://purl.org/vocab/cpsv#',                   'cpsv'],
  ['http://data.europa.eu/eli/ontology#',           'eli'],
  ['http://www.w3.org/ns/locn#',                    'locn'],
  ['http://www.opengis.net/ont/geosparql#',         'geo'],
  ['http://purl.org/dc/elements/1.1/',              'dc'],
  ['http://www.w3.org/2006/vcard/ns#',              'vcard'],
  ['http://www.w3.org/ns/prov#',                    'prov'],
  ['http://purl.org/linked-data/cube#',             'qb'],
  ['http://www.w3.org/ns/person#',                  'person']
];

// Convert a full class URI to prefix:LocalName notation (e.g. cv:ContactPoint).
// Falls back to just the local name if the namespace is unknown.
function uriToQName(uri) {
  if (!uri) return uri;
  const splitIdx = Math.max(uri.lastIndexOf('#'), uri.lastIndexOf('/'));
  if (splitIdx === -1) return uri;
  const namespace = uri.slice(0, splitIdx + 1);
  const localName = uri.slice(splitIdx + 1);
  if (!localName) return uri;
  const match = KNOWN_PREFIXES.find(([ns]) => ns === namespace);
  return match ? `${match[1]}:${localName}` : localName;
}

// Compute the diff between two arrays, matching items by a key function.
// Returns { onlyInA, shared, onlyInB } where shared items come from listA.
function computeDiff(listA, listB, keyFn) {
  const a = listA || [];
  const b = listB || [];
  const keysB = new Set(b.map(keyFn));
  const keysA = new Set(a.map(keyFn));
  return {
    onlyInA:  a.filter(item => !keysB.has(keyFn(item))),
    shared:   a.filter(item =>  keysB.has(keyFn(item))),
    onlyInB:  b.filter(item => !keysA.has(keyFn(item))),
  };
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
  const [descriptionExpanded, setDescriptionExpanded] = useState(false);
  const ontologyFromResults = ontologies.find(o => slugifyTitle(o.title) === slug);
  const ontology = fetchedOntology || ontologyFromResults;
  const navigate = useNavigate();

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  useEffect(() => {
    setLoading(true);
    setError(null);
    setFetchedOntology(null);

    fetch(`${API_BASE}/api/ontology`, {
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
  }, [slug]);

  if (loading && !ontology) return <div className="ontology-detail-bg"><div className="ontology-detail-card"><h2>Loading...</h2></div></div>;
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
          {(() => {
            const words = ontology.description ? ontology.description.split(/\s+/) : [];
            const isLong = words.length > 200;
            const displayed = isLong && !descriptionExpanded
              ? words.slice(0, 200).join(' ') + '...'
              : ontology.description;
            return (
              <>
                {displayed}
                {isLong && (
                  <button
                    className="description-toggle-btn"
                    onClick={() => setDescriptionExpanded(prev => !prev)}
                  >
                    {descriptionExpanded ? 'Hide full description' : 'Show full description'}
                  </button>
                )}
              </>
            );
          })()}
        </div>
        <div className="ontology-detail-section">
          <h3>Main Classes</h3>
          {ontology.mainClasses && ontology.mainClasses.length > 0 ? (
            <ul className="ontology-detail-keywords">
              {ontology.mainClasses.map((cls, idx) => (
                <li key={idx}>
                  <a href={cls.uri} target="_blank" rel="noopener noreferrer" className="class-uri-link">
                    {uriToQName(cls.uri) || cls.label || cls.uri}
                  </a>
                </li>
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
        
        {ontology.requiringAssets && ontology.requiringAssets.length > 0 && (
          <div className="ontology-detail-section">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                 onClick={() => toggleSection('reusedBy')}>
              <h3>This ontology is reused by ({ontology.requiringAssets.length})</h3>
              <span style={{ fontSize: '1.2rem', color: '#075CA8' }}>
                {expandedSections.reusedBy ? '−' : '+'}
              </span>
            </div>
            {expandedSections.reusedBy && (
              <ul className="ontology-detail-keywords">
                {ontology.requiringAssets.map((onto, idx) => {
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
        <button
          className="ontology-detail-meta-box compare-with-box"
          onClick={() => navigate(`/compare?a=${encodeURIComponent(ontology.uri)}`)}
        >
          ⇄ 
          Click here to compare ontologies
        </button>
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
            {ontology.requiringAssets && ontology.requiringAssets.length > 0 && (
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
                  <div style={{ fontWeight: '600', marginBottom: '4px', color: '#075CA8', fontSize: '0.95rem' }}>Organisation</div>
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
  const [compareSelection, setCompareSelection] = useState([]);

  // Clear selection whenever a new set of results arrives
  useEffect(() => { setCompareSelection([]); }, [results]);

  const toggleCompare = (e, onto) => {
    e.stopPropagation();
    setCompareSelection(prev => {
      if (prev.some(s => s.uri === onto.uri)) return prev.filter(s => s.uri !== onto.uri);
      if (prev.length >= 2) return prev;
      return [...prev, onto];
    });
  };
  const handleKeyDown = async (e) => {
    if (e.key === 'Enter') {
      setSubmittedQuery(search);
      setLoading(true);
      setError(null);
      setResults([]);
      try {
        const response = await fetch(`${API_BASE}/api/search`, {
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
      const response = await fetch(`${API_BASE}/api/search`, {
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
            results.map((onto, idx) => {
              const isSelected = compareSelection.some(s => s.uri === onto.uri);
              const isDisabled = !isSelected && compareSelection.length >= 2;
              return (
                <div
                  className={`ontology-card${isSelected ? ' ontology-card--selected' : ''}`}
                  key={idx}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/ontology/${encodeURIComponent(onto.uri)}`)}
                >
                  <div className="ontology-card-header">
                    <span className="ontology-card-title">{onto.title}</span>
                    <button
                      className={`compare-toggle${isSelected ? ' compare-toggle--checked' : ''}${isDisabled ? ' compare-toggle--disabled' : ''}`}
                      onClick={e => toggleCompare(e, onto)}
                      disabled={isDisabled}
                      title={isSelected ? 'Remove from comparison' : isDisabled ? 'Deselect one to add this' : 'Add to comparison'}
                    >
                      {isSelected ? '✓' : '+'}
                    </button>
                  </div>
                  {onto.publishers && onto.publishers.length > 0 && (
                    <div className="ontology-card-main-classes">
                      <span className="ontology-card-main-classes-title">Publisher</span>
                      {onto.publishers.slice(0, 3).map((publisher, i) => (
                        <span className="ontology-card-main-class-tag" key={i} title={publisher.length > 30 ? publisher : undefined}>
                          {truncatePublisher(publisher)}
                        </span>
                      ))}
                    </div>
                  )}
                  {onto.description && (
                    <div className="ontology-card-description">
                      {truncateToWords(onto.description)}
                    </div>
                  )}
                  {onto.requiringAssets && onto.requiringAssets.length > 0 && (
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
                        <span className="ontology-card-subsection-title-grey">Organisation</span>
                        {(() => {
                          const uniquePublishers = getUniqueRequiringPublisherNames(onto.requiringPublisherNames);
                          return uniquePublishers.slice(0, 3).map((pub, i) => (
                            <span className="ontology-card-main-class-tag" key={i} title={pub.length > 30 ? pub : undefined}>
                              {truncatePublisher(pub)}
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
              );
            })
          )}
        </div>
      )}

      {compareSelection.length > 0 && (
        <div className="compare-sticky-bar">
          <div className="compare-sticky-selection">
            {compareSelection.length === 1 ? (
              <>
                <span className="compare-sticky-item">{compareSelection[0].title}</span>
                <span className="compare-sticky-hint">— select one more to compare</span>
              </>
            ) : (
              <>
                <span className="compare-sticky-item">{compareSelection[0].title}</span>
                <span className="compare-sticky-vs">vs</span>
                <span className="compare-sticky-item">{compareSelection[1].title}</span>
              </>
            )}
          </div>
          <div className="compare-sticky-actions">
            <button className="compare-sticky-clear" onClick={() => setCompareSelection([])}>
              ✕ Clear
            </button>
            {compareSelection.length === 2 && (
              <button
                className="compare-sticky-btn"
                onClick={() => navigate(`/compare?a=${encodeURIComponent(compareSelection[0].uri)}&b=${encodeURIComponent(compareSelection[1].uri)}`)}
              >
                Compare →
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function CompareView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const slugA = searchParams.get('a');
  const slugB = searchParams.get('b');

  const [ontoA, setOntoA] = useState(null);
  const [ontoB, setOntoB] = useState(null);
  const [loadingA, setLoadingA] = useState(false);
  const [loadingB, setLoadingB] = useState(false);
  const [errorA, setErrorA] = useState(null);
  const [errorB, setErrorB] = useState(null);

  const [queryA, setQueryA] = useState('');
  const [queryB, setQueryB] = useState('');
  const [suggestionsA, setSuggestionsA] = useState([]);
  const [suggestionsB, setSuggestionsB] = useState([]);
  const [searchingA, setSearchingA] = useState(false);
  const [searchingB, setSearchingB] = useState(false);
  const debounceA = useRef(null);
  const debounceB = useRef(null);

  // Fetch ontology A whenever its slug changes
  useEffect(() => {
    if (!slugA) { setOntoA(null); setErrorA(null); return; }
    setLoadingA(true);
    setErrorA(null);
    fetch(`${API_BASE}/api/ontology`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: slugA })
    })
      .then(res => { if (!res.ok) throw new Error('Ontology not found'); return res.json(); })
      .then(data => { setOntoA(data); setLoadingA(false); })
      .catch(err => { setErrorA(err.message); setLoadingA(false); });
  }, [slugA]);

  // Fetch ontology B whenever its slug changes
  useEffect(() => {
    if (!slugB) { setOntoB(null); setErrorB(null); return; }
    setLoadingB(true);
    setErrorB(null);
    fetch(`${API_BASE}/api/ontology`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: slugB })
    })
      .then(res => { if (!res.ok) throw new Error('Ontology not found'); return res.json(); })
      .then(data => { setOntoB(data); setLoadingB(false); })
      .catch(err => { setErrorB(err.message); setLoadingB(false); });
  }, [slugB]);

  const doSearch = (query, setSuggestions, setSearching, debounceRef) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!query.trim()) { setSuggestions([]); return; }
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(`${API_BASE}/api/search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query })
        });
        const data = await res.json();
        setSuggestions(Array.isArray(data) ? data.slice(0, 8) : []);
      } catch {
        setSuggestions([]);
      } finally {
        setSearching(false);
      }
    }, 300);
  };

  const selectOntology = (slot, onto) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      next.set(slot, onto.uri);  // URLSearchParams encodes automatically
      return next;
    });
    if (slot === 'a') { setQueryA(''); setSuggestionsA([]); }
    else              { setQueryB(''); setSuggestionsB([]); }
  };

  const clearSlot = (slot) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      next.delete(slot);
      return next;
    });
  };

  const renderSlot = (
    label, slot,
    slug, onto, loading, error,
    query, setQuery, suggestions, setSuggestions, searching, setSearching, debounceRef
  ) => (
    <div className="compare-slot">
      <div className="compare-slot-label">{label}</div>
      {slug && onto ? (
        <div className="compare-slot-selected">
          <span className="compare-slot-title">{onto.title}</span>
          <button className="compare-slot-clear" onClick={() => clearSlot(slot)} title="Change selection">✕</button>
        </div>
      ) : slug && loading ? (
        <div className="compare-slot-selected compare-slot-loading">Loading…</div>
      ) : slug && error ? (
        <div className="compare-slot-selected compare-slot-error">{error}</div>
      ) : (
        <div className="compare-slot-search">
          <input
            type="text"
            className="compare-slot-input"
            placeholder="Search for an ontology…"
            value={query}
            onChange={e => {
              setQuery(e.target.value);
              doSearch(e.target.value, setSuggestions, setSearching, debounceRef);
            }}
            onBlur={() => setTimeout(() => setSuggestions([]), 150)}
          />
          {(searching || suggestions.length > 0) && (
            <ul className="compare-slot-dropdown">
              {searching && <li className="compare-slot-dropdown-loading">Searching…</li>}
              {suggestions.map((s, i) => (
                <li
                  key={i}
                  className="compare-slot-dropdown-item"
                  onMouseDown={() => selectOntology(slot, s)}
                >
                  <span className="compare-slot-dropdown-title">{s.title}</span>
                  {s.publishers && s.publishers.length > 0 && (
                    <span className="compare-slot-dropdown-publisher">
                      {truncatePublisher(s.publishers[0])}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );

  return (
    <div className="compare-view">
      <div className="compare-view-header">
        <button className="compare-back-btn" onClick={() => navigate('/')}>
          ← Back to search
        </button>
        <h2>Compare Ontologies</h2>
      </div>

      <div className="compare-selector">
        {renderSlot('Ontology A', 'a', slugA, ontoA, loadingA, errorA, queryA, setQueryA, suggestionsA, setSuggestionsA, searchingA, setSearchingA, debounceA)}
        <div className="compare-vs">vs</div>
        {renderSlot('Ontology B', 'b', slugB, ontoB, loadingB, errorB, queryB, setQueryB, suggestionsB, setSuggestionsB, searchingB, setSearchingB, debounceB)}
      </div>

      {!slugA || !slugB ? (
        <div className="compare-placeholder">
          <p>Select two ontologies above to start comparing.</p>
        </div>
      ) : (loadingA || loadingB) ? (
        <div className="compare-placeholder"><p>Loading…</p></div>
      ) : (errorA || errorB) ? (
        <div className="compare-placeholder compare-error"><p>{errorA || errorB}</p></div>
      ) : ontoA && ontoB ? (
        <div className="compare-content">

          {/* ── Section 1: Metadata ─────────────────────────────── */}
          <div className="compare-section">
            <h3 className="compare-section-title">Overview</h3>
            <div className="compare-columns">

              {[ontoA, ontoB].map((onto, i) => (
                <div key={i} className="compare-meta-card">
                  <div className="compare-meta-title">{onto.title}</div>

                  <div className="compare-meta-row">
                    <span className="compare-meta-label">Publisher</span>
                    {onto.publishers && onto.publishers.length > 0 ? (
                      <span className="compare-meta-value">
                        {onto.publishers.join(', ')}
                      </span>
                    ) : (
                      <span className="compare-meta-empty">Not listed</span>
                    )}
                  </div>

                  <div className="compare-meta-row">
                    <span className="compare-meta-label">Reused by</span>
                    {(() => {
                      const locs = getUniqueRequiringLocations(onto.requiringLocations);
                      return locs.length > 0 ? (
                        <span className="compare-meta-value compare-meta-flags">
                          {locs.map((loc, j) => {
                            const code = getCountryCode(loc);
                            const name = getCountryLabel(loc);
                            return (
                              <span key={j} className="compare-meta-flag-tag">
                                {code && <span className={`fi fi-${code}`}></span>}
                                {name}
                              </span>
                            );
                          })}
                        </span>
                      ) : (
                        <span className="compare-meta-empty">None on record</span>
                      );
                    })()}
                  </div>

                  <div className="compare-meta-row compare-meta-desc-row">
                    <span className="compare-meta-label">Description</span>
                    <span className="compare-meta-value compare-meta-desc">
                      {truncateToWords(onto.description, 50) || <em className="compare-meta-empty">No description</em>}
                    </span>
                  </div>
                </div>
              ))}

            </div>
          </div>

          {/* ── Section 2: Structural Metadata (Reused Ontologies) ── */}
          {(() => {
            const { onlyInA, shared, onlyInB } = computeDiff(
              ontoA.reusedOntologies,
              ontoB.reusedOntologies,
              item => item.uri
            );
            const renderDiffItem = (item) => (
              <li key={item.uri} className="compare-diff-item">
                <button
                  className="compare-diff-link"
                  onClick={() => navigate(`/ontology/${encodeURIComponent(item.uri)}`)}
                >
                  {item.title || item.uri}
                </button>
              </li>
            );
            return (
              <div className="compare-section">
                <h3 className="compare-section-title">Reused Ontologies</h3>
                <div className="compare-diff-columns">

                  <div className="compare-diff-col compare-diff-col--unique">
                    <div className="compare-diff-col-header">
                      <span className="compare-diff-col-onto-label">{ontoA.title}</span>
                      <span className="compare-diff-count">{onlyInA.length}</span>
                    </div>
                    {onlyInA.length === 0
                      ? <span className="compare-meta-empty">None unique</span>
                      : <ul className="compare-diff-list">{onlyInA.map(renderDiffItem)}</ul>}
                  </div>

                  <div className="compare-diff-col compare-diff-col--shared">
                    <div className="compare-diff-col-header">
                      <span>In both</span>
                      <span className="compare-diff-count">{shared.length}</span>
                    </div>
                    {shared.length === 0
                      ? <span className="compare-meta-empty">No overlap</span>
                      : <ul className="compare-diff-list">{shared.map(renderDiffItem)}</ul>}
                  </div>

                  <div className="compare-diff-col compare-diff-col--unique">
                    <div className="compare-diff-col-header">
                      <span className="compare-diff-col-onto-label">{ontoB.title}</span>
                      <span className="compare-diff-count">{onlyInB.length}</span>
                    </div>
                    {onlyInB.length === 0
                      ? <span className="compare-meta-empty">None unique</span>
                      : <ul className="compare-diff-list">{onlyInB.map(renderDiffItem)}</ul>}
                  </div>

                </div>
              </div>
            );
          })()}

          {/* ── Section 3: Semantic Metadata (Classes) ─────────── */}
          {(() => {
            const { onlyInA, shared, onlyInB } = computeDiff(
              ontoA.mainClasses || [],
              ontoB.mainClasses || [],
              item => item.uri
            );
            const renderClassItem = (item) => (
              <li key={item.uri} className="compare-diff-item">
                <a href={item.uri} target="_blank" rel="noopener noreferrer" className="compare-class-tag class-uri-link">
                  {uriToQName(item.uri) || item.label || item.uri}
                </a>
              </li>
            );
            return (
              <div className="compare-section">
                <h3 className="compare-section-title">Classes</h3>
                <div className="compare-diff-columns">

                  <div className="compare-diff-col compare-diff-col--unique">
                    <div className="compare-diff-col-header">
                      <span className="compare-diff-col-onto-label">{ontoA.title}</span>
                      <span className="compare-diff-count">{onlyInA.length}</span>
                    </div>
                    {onlyInA.length === 0
                      ? <span className="compare-meta-empty">None unique</span>
                      : <ul className="compare-diff-list">{onlyInA.map(renderClassItem)}</ul>}
                  </div>

                  <div className="compare-diff-col compare-diff-col--shared">
                    <div className="compare-diff-col-header">
                      <span>In both</span>
                      <span className="compare-diff-count">{shared.length}</span>
                    </div>
                    {shared.length === 0
                      ? <span className="compare-meta-empty">No overlap</span>
                      : <ul className="compare-diff-list">{shared.map(renderClassItem)}</ul>}
                  </div>

                  <div className="compare-diff-col compare-diff-col--unique">
                    <div className="compare-diff-col-header">
                      <span className="compare-diff-col-onto-label">{ontoB.title}</span>
                      <span className="compare-diff-count">{onlyInB.length}</span>
                    </div>
                    {onlyInB.length === 0
                      ? <span className="compare-meta-empty">None unique</span>
                      : <ul className="compare-diff-list">{onlyInB.map(renderClassItem)}</ul>}
                  </div>

                </div>
              </div>
            );
          })()}

        </div>
      ) : null}
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

  const location = useLocation();

  return (
    <>
      <nav className="navbar">
        <div className="navbar-content">
          <div className="logo-title-container">
            <img
              src={`${BASE_PATH}/semic-logo-cropped.png`}
              alt="Semantic Registry Logo"
              className="navbar-logo"
            />
            <h1 onClick={handleTitleClick}>The Semantic Registry</h1>
          </div>
          <div className="navbar-links">
            <Link
              to="/compare"
              className={`navbar-link${location.pathname === '/compare' ? ' navbar-link--active' : ''}`}
            >
              ⇄ Compare
            </Link>
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
        <Route path="/compare" element={<CompareView />} />
      </Routes>
    </>
  );
}

export default function AppWithRouter() {
  return (
    <Router basename="/semantic-registry">
      <App />
    </Router>
  );
} 