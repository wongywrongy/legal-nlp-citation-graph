# Legal Citation Graph

Local-first tool for law students and researchers to ingest a private corpus
of legal opinions, extract citations, and explore the network — both by
**citation links** (who cites whom) and by **semantic similarity** (which
cases read alike), all running on your own machine.

## What it does

- **Ingest**: drag-and-drop PDFs through the web UI; backend extracts text,
  parses citations with `eyecite`, and resolves short/supra/id forms back to
  their full citations.
- **Link**: deterministic reporter/volume/page matching; LLM tie-break only
  for ambiguous candidates (optional, off by default).
- **Embed**: every document is vectorised locally with
  `sentence-transformers` (`all-mpnet-base-v2`, 768-dim, CPU only).
- **Visualise**: Sigma.js + Graphology canvas with two distinct edge types —
  solid blue citation arrows, dashed-style green semantic-similarity edges.
- **Search**: type a query in the top bar and the graph camera centres on
  the most semantically similar cases.
- **Inspect**: click any node, edge, or citation; the right-hand inspector
  shows the confidence breakdown, semantic neighbours, and resolution notes.

## Stack

| Layer       | Technology                                                |
| ----------- | --------------------------------------------------------- |
| Backend     | FastAPI (async), SQLAlchemy 2.0, ARQ workers              |
| Database    | Postgres 16 with **pgvector** extension                   |
| Citations   | `eyecite` (full + resolution pass for short forms)        |
| PDF         | PyMuPDF                                                   |
| Embeddings  | `sentence-transformers` `all-mpnet-base-v2` (CPU)         |
| LLM (opt.)  | Anthropic `claude-opus-4-7` for ambiguous citations       |
| Frontend    | Next.js 14 + Tailwind + shadcn/ui                         |
| Graph viz   | Sigma.js + Graphology + ForceAtlas2                       |
| Container   | Docker Compose (single `up` boots everything)             |

Local-first guarantees: no cloud DB, no managed embedding APIs, no telemetry.
The Anthropic and CourtListener integrations are both feature-flagged off by
default.

## Quick start

```bash
git clone <repo>
cd legal-nlp-citation-graph
cp env.example .env
# (Optional) set ANTHROPIC_API_KEY for LLM tie-break,
# COURTLISTENER_API_KEY for the seed script's higher rate limit.

make up            # build + start the dev stack in the background
make seed          # pull 50 SCOTUS opinions from CourtListener
make logs-worker   # follow PDF parse / embed progress
```

That's the whole loop. `make` with no args lists every target.

| Service                     | URL                            |
| --------------------------- | ------------------------------ |
| Frontend                    | http://localhost:3000          |
| API                         | http://localhost:8001          |
| Swagger UI                  | http://localhost:8001/docs     |
| Health                      | http://localhost:8001/health   |

### Common workflows

| Need to...                                | Command          |
| ----------------------------------------- | ---------------- |
| Start the dev stack                       | `make up`        |
| Tail all logs                             | `make logs`      |
| Tail just the worker                      | `make logs-worker` |
| Seed 50 SCOTUS opinions                   | `make seed`      |
| Re-embed corpus after model change        | `make reembed`   |
| Open psql on the dev DB                   | `make psql`      |
| Open a shell in the backend container     | `make shell-backend` |
| Restart everything without rebuild        | `make restart`   |
| Rebuild backend + worker, restart         | `make rebuild`   |
| Stop (preserve DB + PDFs)                 | `make down`      |
| Stop AND wipe everything (asks for y/N)   | `make reset`     |
| Run pytest inside the backend             | `make test`      |
| Run the production-ish stack (with nginx) | `make prod-up`   |

The Makefile wraps `docker compose -f docker-compose.dev.yml ...` so you
don't have to type the file flag every time. Both compose files still work
directly if you prefer.

## Architecture

```
┌────────────┐  upload   ┌────────────┐  enqueue  ┌──────────────┐
│ Next.js UI │ ────────▶ │   API      │ ────────▶ │  Redis (ARQ) │
└─────┬──────┘           └─────┬──────┘           └──────┬───────┘
      │                        │                         │
      │  /v1, /api             │                         │
      ▼                        ▼                         ▼
┌────────────┐           ┌────────────┐           ┌────────────────┐
│ Sigma.js   │ ◀──────── │ pgvector   │ ◀──────── │ ARQ workers    │
│ +graphology│   /graph  │ Postgres   │   write   │ • PDF parse    │
└────────────┘           └────────────┘           │ • eyecite +    │
                                                  │   resolve      │
                                                  │ • embed        │
                                                  │ • cosine top-K │
                                                  └────────────────┘
```

A single ingest triggers, in order: text extraction → citation parsing +
resolution → deterministic linking (with optional LLM tie-break) → embedding
→ refresh of `semantic_similarity` rows for the new document. The graph
endpoint reads citation edges from `citations`; the new
`/api/similar-edges` endpoint reads symmetric semantic edges from
`semantic_similarity`. The frontend merges them and renders both layers.

### Endpoints

```
GET  /health                           # db + redis status
GET  /v1/documents                     # paginated list
GET  /v1/documents/{id}                # detail + citations
GET  /v1/documents/{id}/pdf            # stream the PDF
GET  /v1/documents/{id}/status         # processing state
POST /v1/ingest                        # multipart PDF upload
POST /v1/process /v1/process/{id}      # batch / single re-process
GET  /v1/graph?min_confidence=…        # citation graph
GET  /v1/stats                         # corpus aggregates

GET  /api/similar/{doc_id}             # top-k semantic neighbours
POST /api/search   {q, limit, min_similarity}
GET  /api/similar-edges?min_similarity # symmetric edges, for the graph
```

## Local development without Docker

```bash
# Install Postgres 16 + pgvector (Mac with Homebrew):
brew install postgresql@16
brew install pgvector
brew services start postgresql@16
createdb citations -O citations
psql citations -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Redis
brew install redis && brew services start redis

# Python deps
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-test.txt

# Schema
alembic upgrade head

# Terminal A — API
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal B — worker
arq backend.workers.WorkerSettings

# Terminal C — frontend
cd frontend && npm install && npm run dev
```

The API is at `http://localhost:8000` (or `:8001` when run via Docker so
the host port doesn't conflict with anything else listening on 8000).

## Tests

```bash
pytest                              # full suite (sqlite-backed, no pgvector)
pytest -m "unit and fast"           # tight feedback loop
pytest -m requires_pgvector         # vector-dependent tests; run inside Docker:
docker compose -f docker-compose.dev.yml run --rm backend pytest -m requires_pgvector
```

Tests live in `tests/` and use synthetic PDFs (PyMuPDF generates them in
fixtures). The test suite uses sqlite via `with_variant` so embedding
columns don't break schema creation, but actual vector arithmetic requires
the docker dev stack.

## Configuration

All settings live in `backend/config.py` (pydantic-settings, reads `.env`).

```bash
# Database
DATABASE_URL=postgresql+asyncpg://citations:citations@localhost:5432/citations
DATABASE_URL_SYNC=postgresql+psycopg2://citations:citations@localhost:5432/citations

# Storage / API / queue
PDF_STORAGE_PATH=./data/pdfs
API_PORT=8000
CORS_ORIGINS=http://localhost:3000
REDIS_URL=redis://localhost:6379

# Embeddings (sentence-transformers, CPU)
FEATURE_EMBEDDINGS=true
EMBEDDING_MODEL=all-mpnet-base-v2
EMBEDDING_DIM=768
EMBEDDING_TOP_K=25
SIMILARITY_THRESHOLD_DEFAULT=0.75

# LLM tie-break (off-by-default — set ANTHROPIC_API_KEY to enable)
ANTHROPIC_API_KEY=
LLM_MODEL=claude-opus-4-7
FEATURE_LLM_RESOLVER=true

# Optional CourtListener enrichment
FEATURE_EXTERNAL_ENRICHMENT=false
COURTLISTENER_API_KEY=

# Graph defaults
MIN_CONFIDENCE_DEFAULT=0.7

LOG_LEVEL=INFO
```

## Hardware notes

- **RAM**: the embedding model (~420 MB) plus tokenisation buffers means
  ~800 MB resident. Allocate at least 4 GB to Docker.
- **Disk**: each document persists its `full_text`; budget ~1 KB/page in
  Postgres on top of the source PDFs.
- **CPU**: encoding a 5-page opinion takes ~150 ms on an M1 / 2020-class
  laptop. The embedding model weights are baked into the image so first
  request doesn't pay the download.

## Project layout

```
backend/
  main.py                   # FastAPI app + /v1 + /api routes
  config.py                 # pydantic-settings
  database.py               # sync + async engines
  models.py                 # Document, Citation, SemanticSimilarity
  pdf_processor.py          # PyMuPDF extraction + page span resolution
  citation_parser.py        # eyecite + resolve_citations()
  document_processor.py     # Sync orchestrator (parse → store → link)
  async_processor.py        # asyncio.to_thread wrapper for ARQ
  workers.py                # process_pdf_job, embed_document_job, …
  embeddings.py             # sentence-transformers + pgvector queries
  llm_resolver.py           # Anthropic tie-break (feature-gated)
  courtlistener.py          # API client (enrichment + seed list_opinions)
  schemas.py                # Pydantic response shapes
  exceptions.py             # Structured error responses

alembic/versions/
  0001_initial_schema.py
  0002_pgvector_and_similarity.py

scripts/
  seed.py                   # 50 SCOTUS opinions from CourtListener
  health_check.py           # one-shot system health verification
  run_test_suite.py         # category-based pytest runner
  start_backend.py          # local non-Docker dev launcher
  deploy.sh / deploy.ps1    # Linux + Windows deploy helpers
  test-docker.sh            # docker stack smoke test

frontend/
  src/app/                  # Next.js routes (dashboard, /graph, /documents, …)
  src/components/CitationGraph.tsx   # Sigma.js + Graphology canvas
  src/components/shell/              # AppShell, TopBar, LeftRail, InspectorPanel
  src/components/primitives/         # ConfidenceBadge, CitationText, …
  src/lib/api.ts            # documentApi, graphApi, ingestApi, statsApi, searchApi
  src/lib/graph-data.ts     # buildSigmaGraph()
  src/lib/inspector-store.ts
  src/lib/graph-store.ts    # camera focus state shared between TopBar + graph

tests/
  test_*.py                 # PDF parser, citation parser (incl. resolution),
                            # API endpoints, models, integration

docker-compose.yml          # production stack (pgvector, redis, api, worker,
                            # frontend, nginx, optional `seed` profile)
docker-compose.dev.yml      # dev stack (same minus nginx, with --reload)
Dockerfile                  # builds the API + worker image; pre-warms the
                            # sentence-transformers model
```

## Troubleshooting

- **`relation "documents" does not exist`** — Alembic didn't run. The dev
  compose runs `alembic upgrade head` on startup; if you started from a
  clean DB but skipped the API entrypoint, `docker compose exec backend
  alembic upgrade head`.
- **`extension "vector" is not available`** — you're on stock `postgres:16`
  rather than `pgvector/pgvector:pg16`. The compose files already use the
  pgvector image; rebuild.
- **`Cannot find module 'tailwindcss-animate'`** — anonymous frontend
  volume cached an old `node_modules`. Bring the stack down with `-v` then
  back up: `docker compose -f docker-compose.dev.yml down -v && up --build`.
- **Embedding worker runs but no `/api/similar` results** — embeddings
  produce rows only after `embed_document_job` completes for *both*
  endpoints of a similarity edge. Wait for the worker queue to drain.

## License

The system does not download copyrighted content, hallucinate links, or
rely on unproven legal NLP approaches. See `cursor/product/non_goals.md`.
