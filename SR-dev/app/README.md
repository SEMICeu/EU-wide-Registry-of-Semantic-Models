# App Structure and Setup

This folder contains the Semantic Registry application split into separate parts:

- `sr-frontend`: React frontend (UI, static assets, build output)
- `sr-backend`: Express backend (API + static file serving)
- `chatbot`: Chatbot service (GraphRAG + Neo4j integration)
- `docker-compose.yml`: orchestration for Neo4j, chatbot, and semantic registry
- `Dockerfile`: image build for the `semantic-registry` service

## Folder Layout

```text
app/
  sr-frontend/
    src/
    public/
    data/
    package.json
  sr-backend/
    backend.js
    package.json
  chatbot/
    Dockerfile
    README.md
    ...
  docker-compose.yml
  Dockerfile
```

## Local Development

Run backend and frontend in separate terminals.

### 1) Backend

```powershell
cd "C:\Users\Dean Terneu\Documents\PwC\Projects\SEMIC\SRM\EU-wide-Registry-of-Semantic-Models\SR-dev\app\sr-backend"
npm install
npm run start-backend
```

Backend runs on `http://localhost:4000`.

### 2) Frontend

```powershell
cd "C:\Users\Dean Terneu\Documents\PwC\Projects\SEMIC\SRM\EU-wide-Registry-of-Semantic-Models\SR-dev\app\sr-frontend"
npm install
$env:REACT_APP_API_URL="http://localhost:4000/semantic-registry"
npm start
```

Frontend runs on `http://localhost:3000/semantic-registry`.

## Docker Compose

From the `app` folder:

```powershell
cd "C:\Users\Dean Terneu\Documents\PwC\Projects\SEMIC\SRM\EU-wide-Registry-of-Semantic-Models\SR-dev\app"
docker compose up --build
```

Application URL: `http://localhost:8080/semantic-registry`

The chatbot service is built locally from `app/chatbot` and loads runtime variables from `app/chatbot/.env` via `env_file`.

### Services in Compose

- `neo4j` (ports `7555`, `7688`)
- `chatbot` (port `8050`)
- `semantic-registry` (port `8080` -> container `4000`)

## Stop Commands

- Local processes: `Ctrl + C` in each terminal
- Compose stack:

```powershell
docker compose down
```

## Notes

- The backend serves built frontend files from `public/` in production/container builds.
- For local development, React dev server is recommended for frontend hot reload.
- For containers, chatbot should use `NEO4J_URI=bolt://neo4j:7687` (service-to-service network), not `localhost`.

## Troubleshooting

### Chatbot restart loop after code/env changes

Rebuild and recreate chatbot cleanly:

```powershell
docker compose down
docker compose build --no-cache chatbot
docker compose up --force-recreate
```

### Chatbot cannot connect to Neo4j

If logs show connection attempts to `localhost:7688`, it means local settings leaked into container runtime. Ensure:

- `docker-compose.yml` sets `NEO4J_URI=bolt://neo4j:7687` for `chatbot`
- chatbot `.env` is used only to fill missing values, not to override compose container networking settings
