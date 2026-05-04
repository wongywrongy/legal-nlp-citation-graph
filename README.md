# Legal Citation Graph (Currently stagnant due to lack of time)

A local-first tool for law students and researchers to ingest a private
corpus of legal opinions, extract citations, and explore the network — both
by **citation links** (who cites whom) and by **semantic similarity**
(which cases read alike). Everything runs on your own machine: no cloud
DB, no managed embedding APIs, no telemetry.

---

## What you'll need

| Requirement              | Why                                          |
| ------------------------ | -------------------------------------------- |
| Docker Desktop (≥ 4.0)   | The whole stack runs in containers           |
| `make`                   | Wraps the long compose commands              |
| ~5 GB free disk          | Postgres + pgvector + sentence-transformers  |
| ≥ 4 GB RAM for Docker    | The embedding model alone resides at ~800 MB |
| (Optional) CourtListener API key | Higher rate limits when seeding      |

`make` ships with macOS and most Linux distros. On Windows, install via
WSL2 or `choco install make`.

> **Tip:** Get a free CourtListener API key at
> [courtlistener.com/help/api/rest/](https://www.courtlistener.com/help/api/rest/).
> The seed scripts work without one, but anonymous rate limits are tight.

---

## First run (≈ 5 minutes)

```bash
git clone <repo>
cd legal-nlp-citation-graph
cp env.example .env
make up
```

`make up` builds the images and starts everything in the background.
First build takes 2–4 minutes (mostly the sentence-transformers model
download — it gets baked into the image so subsequent boots are instant).

Wait until the dev URLs are reachable:

| Service    | URL                          |
| ---------- | ---------------------------- |
| Frontend   | http://localhost:3000        |
| API        | http://localhost:8001        |
| API docs   | http://localhost:8001/docs   |
| Health     | http://localhost:8001/health |

Open http://localhost:3000 — you'll see the empty shell. Now seed it.

---

## Seed the corpus

You have three options. Pick whichever matches your goal.

### Option A — Quick demo (50 recent SCOTUS opinions)

```bash
make seed
```

Pulls the 50 most-recently-ingested SCOTUS opinions from CourtListener.
Good for a quick "does it work?" smoke test.

### Option B — The canon (~40 SCOTUS landmarks)

```bash
make seed-landmarks
```

Pulls a curated list of landmark cases — Marbury, Brown, Roe, Miranda,
Heller, Obergefell, Carpenter, etc. Best if you want the graph to look
*meaningful* immediately. Takes ~2 min.

### Option C — Historical spread (decades)

```bash
make seed-historical SEED_ARGS="--year-min=1950 --year-max=2020"
```

Walks decade windows, fetching ~20 opinions per decade so the corpus
spans history evenly. Gives the timeline scrubber a real shape. Drop the
`SEED_ARGS` to default to 1900–present.

### What happens after seeding

The worker queue picks up each new document and runs:

1. **Parse** — PyMuPDF extracts text + page spans
2. **Cite** — `eyecite` extracts and resolves short/supra/id citations
3. **Link** — deterministic reporter/volume/page matching, optional LLM tie-break
4. **Embed** — `all-mpnet-base-v2` produces 768-dim vectors
5. **Similarity** — top-K cosine neighbours written to `semantic_similarity`

Watch progress:

```bash
make logs-worker
```

Wait until you see `embed_document_job` completions slowing — that's when
the graph at http://localhost:3000/graph fills in.

---

## Using the app

| Goal                                  | How                                            |
| ------------------------------------- | ---------------------------------------------- |
| Browse the citation network           | http://localhost:3000/graph                    |
| Search by case name or topic          | Top-bar search box (debounced; lexical fallback covers proper-noun queries like "Riley") |
| Inspect a case                        | Click any node — right panel shows citations, neighbours, confidence |
| Filter by year                        | Drag the timeline scrubber at bottom of /graph |
| Adjust similarity edge density        | Drag the threshold slider above the canvas     |
| Upload your own PDFs                  | http://localhost:3000/upload (drag & drop)     |

The search bar runs three modes automatically: cross-encoder re-rank →
bi-encoder cosine → ILIKE lexical fallback. The badge next to each result
tells you which fired (`Reranked` / no badge / `Title match`).

---

## Daily commands

`make` with no args lists every target. The most-used ones:

```bash
make up                  # start the dev stack
make down                # stop (preserves DB + PDFs)
make reset               # stop AND wipe everything (asks y/N)
make logs                # tail every service
make logs-worker         # tail just the PDF / embed pipeline
make seed                # quick: 50 recent SCOTUS opinions
make seed-landmarks      # ~40 SCOTUS landmarks
make seed-historical     # decade-spread (use SEED_ARGS for ranges)
make migrate             # run alembic upgrade head
make psql                # open psql against the dev DB
make shell-backend       # bash inside the API container
make rebuild             # rebuild backend + worker images
make rebuild-frontend    # rebuild frontend (after package.json changes)
make test                # run pytest inside the backend container
```

---

## Optional features

These are off by default. Flip them on by editing `.env`, then `make restart`.

| Flag                          | What it does                                                                |
| ----------------------------- | --------------------------------------------------------------------------- |
| `FEATURE_LLM_RESOLVER`        | Use Claude (`ANTHROPIC_API_KEY`) to break ties when ≥2 candidate docs match |
| `FEATURE_EXTERNAL_ENRICHMENT` | Fall back to CourtListener for citations the corpus can't resolve. The inspector then shows them as "Not in corpus" with an external link |
| `FEATURE_CROSS_ENCODER`       | Add cross-encoder re-rank on top of bi-encoder search results               |

`COURTLISTENER_API_KEY` and `ANTHROPIC_API_KEY` are read from `.env`. The
flags above are independent — set whichever you want.

---

## Endpoints

```
GET  /health                             # db + redis status
GET  /v1/documents                       # paginated list
GET  /v1/documents/{id}                  # detail + citations
GET  /v1/documents/{id}/pdf              # stream the source PDF
GET  /v1/documents/{id}/cites-out        # resolved outgoing citations
GET  /v1/documents/{id}/cited-by         # incoming citations
GET  /v1/documents/{id}/citations        # all outgoing in 3 states (resolved / external / unresolved)
POST /v1/ingest                          # multipart PDF upload
GET  /v1/graph?min_confidence=…          # citation graph
GET  /v1/stats                           # corpus aggregates

GET  /api/similar/{doc_id}               # top-k semantic neighbours
GET  /api/similar-edges?min_similarity   # symmetric edges for the graph
POST /api/search                         # body {q, limit, min_similarity}
```

Full Swagger UI at http://localhost:8001/docs.

---

## Architecture

```
┌────────────┐  upload   ┌────────────┐  enqueue  ┌──────────────┐
│ Next.js UI │ ────────▶ │   API      │ ────────▶ │  Redis (ARQ) │
└─────┬──────┘           └─────┬──────┘           └──────┬───────┘
      │                        │                         │
      ▼                        ▼                         ▼
┌────────────┐           ┌────────────┐           ┌────────────────┐
│ Sigma.js   │ ◀──────── │ pgvector   │ ◀──────── │ ARQ workers    │
│ +graphology│           │ Postgres   │           │ • PDF parse    │
└────────────┘           └────────────┘           │ • eyecite      │
                                                  │ • link / LLM   │
                                                  │ • embed        │
                                                  │ • cosine top-K │
                                                  └────────────────┘
```

| Layer       | Tech                                                    |
| ----------- | ------------------------------------------------------- |
| Backend     | FastAPI, SQLAlchemy 2.0 (async), ARQ                    |
| Database    | Postgres 16 + pgvector (HNSW cosine index)              |
| Citations   | `eyecite` with `resolve_citations()` parent inheritance |
| PDF         | PyMuPDF                                                 |
| Embeddings  | `sentence-transformers` `all-mpnet-base-v2` (CPU, 768d) |
| Re-ranker   | `cross-encoder/ms-marco-MiniLM-L-6-v2` (CPU)            |
| LLM (opt.)  | Anthropic `claude-opus-4-7`                             |
| Frontend    | Next.js 14, Tailwind, shadcn/ui                         |
| Graph       | Sigma 2 + Graphology + ForceAtlas2 (web worker)         |

`AUDIT.md` is the canonical engineering reference — read it for the
full pipeline, schema, tuning knobs, and known gaps.

---

## Troubleshooting

| Symptom                                         | Fix                                                                  |
| ----------------------------------------------- | -------------------------------------------------------------------- |
| `port 8001 already in use`                      | Edit `API_PORT` in `.env`; restart                                   |
| `relation "documents" does not exist`           | `make migrate`                                                       |
| `extension "vector" is not available`           | `make rebuild` (the compose files already use `pgvector/pgvector:pg16`) |
| `Cannot find module 'tailwindcss-animate'`      | `make rebuild-frontend` (anonymous node_modules volume staleness)    |
| `/api/similar/{id}` returns `[]` for new doc    | Wait for `embed_document_job` to finish for *both* endpoints of each similarity edge — `make logs-worker` |
| `seed` says "0 ingested"                        | The fingerprints already exist; `make reset` to start fresh, or just use a different `--court` / `--topic` |
| Graph is a hairball                             | Drag the similarity-threshold slider up; lower-confidence semantic edges drop off |
| First request to `/api/search` is slow          | Cross-encoder loads on first use (~3s); subsequent calls are warm    |

For anything else, check `make logs` and the structured JSON logs from
`backend` and `worker` will tell you which stage failed.

---

## Tests

```bash
make test                                                # full suite (sqlite-backed)
docker compose -f docker-compose.dev.yml exec backend pytest -m requires_pgvector
```

The unit tests use SQLite via `with_variant` so embedding columns don't
break schema creation. Vector-arithmetic tests are gated behind
`requires_pgvector` and only run inside the Docker dev stack.
