# EU-wide Registry of Semantic Models — Semantic Registry Frontend

A web application for discovering, browsing, and comparing semantic models (ontologies) across EU Member States. It serves as the frontend and backend interface for the [SEMIC](https://joinup.ec.europa.eu/collection/semantic-interoperability-community-semic) Semantic Registry initiative.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Source Files](#source-files)
  - [Backend (backend.js)](#backend-backendjs)
  - [Frontend (src/)](#frontend-src)
  - [Data Mapping Files](#data-mapping-files)
- [Related Modules (SR-dev/)](#related-modules-sr-dev)
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [Deployment with Docker](#deployment-with-docker)
- [Environment Variables](#environment-variables)
- [License](#license)

---

## Overview

The Semantic Registry allows users to:

- **Search** for semantic models published by EU institutions and Member States
- **Browse** detailed metadata for each ontology (descriptions, distributions, classes, languages, publishers)
- **Compare** two ontologies side-by-side, highlighting shared and unique classes and reuse relationships
- **Discover** how ontologies relate to each other through reuse chains

Data is stored as RDF in a [Virtuoso](https://virtuoso.openlinksw.com/) triple store and queried over SPARQL. The frontend uses a thin Express backend to proxy and transform SPARQL results into JSON.

---

## Architecture

```
Browser (React SPA)
      │
      ▼
Express.js server (backend.js)       ← serves static React build + REST API
      │
      ▼
Virtuoso SPARQL endpoint             ← https://health.semic.eu/virtuoso/sparql
      │
  RDF graphs:
    http://semic.registry.eu         (primary)
    http://semic.registry2.eu        (data themes fallback)
```

The React app is built into a `public/` folder. Express serves it as static files and additionally exposes three API endpoints. There is no separate API server needed at runtime — everything runs on a single Node.js process on port **4000**.

---

## Project Structure

```
sr-front-end/sr-front-end/
├── src/                        # React application source
│   ├── App.js                  # Main application (all pages and routing)
│   ├── App.css                 # All UI styles
│   ├── index.js                # React entry point
│   ├── index.css               # Global CSS resets
│   ├── languageMapping.js      # Language IRI → human-readable label
│   ├── dataThemeMapping.js     # EU data theme IRI → label
│   ├── formatMapping.js        # File format IRI → label
│   ├── countryMapping.js       # Country IRI → ISO code + name
│   └── publisherMapping.js     # Publisher IRI → display name
├── public/                     # Static assets served by Express
│   ├── index.html              # HTML shell for the React app
│   ├── semic-logo-cropped.png
│   └── eu-logo.png
├── backend.js                  # Express server + SPARQL query layer
├── Dockerfile                  # Multi-stage Docker build
├── docker-compose.yml          # Container orchestration
├── .dockerignore
├── package.json
└── package-lock.json
```

---

## Source Files

### Backend (`backend.js`)

The Express server has three responsibilities:

1. **Serve the React build** — all files under `public/` are served as static assets at `/semantic-registry`.
2. **Proxy SPARQL queries** — translates REST API calls into SPARQL queries against the Virtuoso endpoint and returns structured JSON.
3. **Cache stats** — the `/stats` endpoint is cached in-memory for one hour to avoid repeated SPARQL aggregations.

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns `200 OK` |
| `GET` | `/semantic-registry/api/stats` | Summary statistics (total ontologies, themes, publishers). Cached 1 hour. |
| `POST` | `/semantic-registry/api/search` | Full-text search with optional `theme` and `publisher` filters. Body: `{ query, theme, publisher }` |
| `POST` | `/semantic-registry/api/ontology` | Full metadata for a single ontology. Body: `{ uri }` |

#### SPARQL graphs used

- `http://semic.registry.eu` — primary graph containing all ontology metadata
- `http://semic.registry2.eu` — fallback graph used for data theme lookups

#### RDF vocabularies queried

`ADMS`, `DCAT`, `DCT`, `FOAF`, `RDFS`, `SKOS`, `OWL`, `CV` (SEMIC Core Vocabularies), `DQV`

---

### Frontend (`src/`)

All pages live inside `App.js` as React functional components with hooks. React Router v6 is used for client-side navigation.

#### Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/semantic-registry/` | `SearchPage` | Home — search bar, filters, results grid, registry stats |
| `/semantic-registry/ontology/:slug` | `OntologyDetail` | Full detail page for one ontology |
| `/semantic-registry/compare` | `CompareView` | Side-by-side comparison of two ontologies |

#### `SearchPage`

- Free-text search input sent to `/api/search`
- Data theme filter (13 EU themes) and publisher filter dropdowns
- Results shown as cards (title, publisher, description, country flags, theme tags)
- Sticky comparison bar at the bottom — up to two ontologies can be queued for comparison
- Registry-wide statistics banner (total ontologies, themes, publishers)

#### `OntologyDetail`

- Fetches full metadata via `/api/ontology`
- Sections: title, publisher, description (collapsible), main classes, distributions (file formats + download links), data themes, keywords, languages
- Sidebar: homepage link, creation/modification dates, URI
- "Reuses" and "Reused by" sections for relationship discovery
- Add-to-compare button

#### `CompareView`

- Two independent search inputs, each selecting one ontology
- **Overview** — side-by-side metadata table
- **Reused Ontologies** — Venn-style columns: only in A / in both / only in B
- **Classes** — same three-column diff layout for ontology classes
- Deep-linkable via URL query parameters (`?a=<uri>&b=<uri>`)

---

### Data Mapping Files

These modules map RDF IRIs to human-readable labels used throughout the UI.

| File | Purpose |
|------|---------|
| `languageMapping.js` | Language IRIs (e.g. `http://id.loc.gov/vocabulary/iso639-1/en`) → `"English"` |
| `dataThemeMapping.js` | EU MDR Data Theme IRIs → theme labels (13 themes) |
| `formatMapping.js` | IANA/MDR format IRIs → `"Turtle"`, `"JSON-LD"`, etc. |
| `countryMapping.js` | Country IRIs → ISO 3166-1 alpha-2 codes + display names |
| `publisherMapping.js` | Known publisher IRIs → display names (W3C, DIGIT, AGID, etc.) |

---

## Related Modules (`SR-dev/`)

The parent repository contains a full data pipeline that feeds the SPARQL endpoint. These modules are independent services and are not required to run the frontend.

| Directory | Language | Purpose |
|-----------|----------|---------|
| `api/` | Python (FastAPI) | Alternative REST API layer over the triple store |
| `harvester/` | Python | Crawls and ingests ontology metadata from Member State sources |
| `enricher/` | Python | Enriches harvested metadata (e.g. resolves publisher names, detects formats) |
| `validator/` | Python | Validates RDF data against SHACL shapes before ingestion |
| `metadata/` | Python | Metadata management utilities |
| `provenance/` | Python | Tracks data lineage and provenance using PROV-O |
| `script/` | Mixed | Utility scripts for one-off data tasks |

Python dependencies for these modules are listed in the root `requirements.txt`.

---

## Configuration

### `package.json` scripts

| Script | Command | Description |
|--------|---------|-------------|
| `start` | `react-scripts start` | Start React development server (port 3000) |
| `build` | `react-scripts build` | Build optimised production bundle into `build/` |
| `start-backend` | `node backend.js` | Start Express server (port 4000) |
| `test` | `react-scripts test` | Run Jest tests |

### Key dependencies

| Package | Version | Role |
|---------|---------|------|
| `react` | 18.2.0 | UI framework |
| `react-router-dom` | 6.22.3 | Client-side routing |
| `express` | 4.18.2 | Backend HTTP server |
| `sparql-http-client` | 3.0.1 | SPARQL query execution |
| `http-proxy-middleware` | 3.0.5 | Dev-mode proxying of API calls |
| `flag-icons` | 7.5.0 | CSS flag icon library |
| `cors` | 2.8.5 | CORS headers for the Express API |

---

## Running Locally

### Prerequisites

- Node.js 18+
- npm 9+
- Network access to `https://health.semic.eu/virtuoso/sparql`

### Development mode

Run the React development server and Express backend concurrently:

```bash
# Terminal 1 — React dev server (hot reload, port 3000)
npm start

# Terminal 2 — Express backend (port 4000)
npm run start-backend
```

The `http-proxy-middleware` configuration in the React app proxies `/semantic-registry/api/*` requests from port 3000 to the Express server on port 4000 during development.

Open [http://localhost:3000/semantic-registry](http://localhost:3000/semantic-registry).

### Production mode (without Docker)

```bash
# Build the React app
npm run build

# Copy the build output to the public folder Express serves
cp -r build/* public/

# Start the Express server
npm run start-backend
```

Open [http://localhost:4000/semantic-registry](http://localhost:4000/semantic-registry).

---

## Deployment with Docker

The included `Dockerfile` uses a two-stage build:

1. **Build stage** — installs all npm dependencies and runs `npm run build`
2. **Production stage** — installs only production dependencies, copies the Express server and the built React app, runs as a non-root `appuser`

### Build and run the image

```bash
# Build image
docker build -t semantic-registry .

# Run container (maps host port 8080 to container port 4000)
docker run -p 8080:4000 --env NODE_ENV=production semantic-registry
```

### Docker Compose (recommended)

```bash
docker compose up --build
```

The `docker-compose.yml` maps port **8080** on the host to port **4000** inside the container and sets `NODE_ENV=production` and `BASE_PATH=/semantic-registry`.

After startup, the application is available at [http://localhost:8080/semantic-registry](http://localhost:8080/semantic-registry).

#### Compose configuration summary

| Setting | Value |
|---------|-------|
| Host port | `8080` |
| Container port | `4000` |
| `NODE_ENV` | `production` |
| `BASE_PATH` | `/semantic-registry` |
| Restart policy | `unless-stopped` |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `4000` | Port the Express server listens on |
| `NODE_ENV` | — | Set to `production` in Docker to disable React dev tooling |
| `BASE_PATH` | `/semantic-registry` | URL prefix for all routes and static assets |

---

## License

Copyright © 2024 European Union. All material in this repository is published under the [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/) licence, unless explicitly otherwise mentioned.
