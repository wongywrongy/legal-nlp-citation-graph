# AUDIT — Citegraph product reference

**Last refreshed:** 2026-04-29 · **Branch:** `dev`

This document is the **current-state reference** for the product, not a
changelog. Read it cold to understand what the system does, how it's
built, and where to tune things. Section 9 has the diagnostic checklist
when something feels broken.

---

## 1. What this product is

A local-first legal research tool. A user (typically a paralegal, law
student, or in-house counsel) curates a private corpus of court opinion
PDFs. The system extracts citations, embeds the text semantically, and
visualises the corpus as a graph: solid blue arrows for explicit
citations, translucent green lines for semantic similarity. Hover any
case to see its neighbourhood; type into search to flashlight matches
on the canvas; click a case to read its summary, its incoming and
outgoing citations, and its semantic neighbours.

Everything runs in Docker Compose — Postgres + pgvector for storage,
sentence-transformers (CPU) for embeddings, Anthropic Claude as an
optional tie-break for ambiguous citations, CourtListener as the seed
data source. No cloud DB, no managed embedding service.

---

## 2. Stack at a glance

| Layer | Library / service | Purpose |
| --- | --- | --- |
| Database | `pgvector/pgvector:pg16` | Postgres + vector extension |
| ORM | SQLAlchemy 2.0 (async + sync) | Routes use async; Alembic uses sync |
| Migrations | Alembic | Three revisions: initial → pgvector → hnsw |
| Web framework | FastAPI 0.110 | Async routes, pydantic v2 schemas |
| PDF parsing | PyMuPDF 1.24 | Text + per-page span offsets |
| Citation extraction | `eyecite` 2.6 + `reporters-db` | Full / short / supra / id citation parsing + resolution |
| Embeddings | `sentence-transformers` 2.7 | `all-mpnet-base-v2` (768d, CPU) — chunked + mean-pooled |
| Re-ranker | sentence-transformers `CrossEncoder` | `ms-marco-MiniLM-L-6-v2` for /api/search |
| LLM tie-break | `anthropic` SDK | `claude-opus-4-7`, gated by `FEATURE_LLM_RESOLVER` |
| Workers | ARQ + Redis | `process_pdf_job`, `embed_document_job`, `enrich_document_job` |
| Frontend | Next.js 14 (App Router) + Tailwind + shadcn/ui | RSC where possible, client where needed |
| Graph data | `graphology` (multi-directed) + `graphology-communities-louvain` | Layout, community detection |
| Graph layout | `graphology-layout` (random/circular) → `forceAtlas2` → `noverlap` | Three-stage pipeline |
| Graph renderer | `sigma` 2.4 + `@react-sigma/core` 3.4 | WebGL canvas |
| Cross-component state | `zustand` | `inspector-store`, `graph-store`, `upload-store` |

All graphology packages are pinned to mutually compatible versions in
`frontend/package.json`. The matrix is fragile across major versions —
when bumping any of them, verify the peer-dep chain.

---

## 3. Repository layout

```
backend/                 — FastAPI app
  main.py                — routes (/v1/*, /api/*)
  config.py              — pydantic-settings, all env vars
  database.py            — sync + async engines
  models.py              — Document, Citation, SemanticSimilarity
  pdf_processor.py       — PyMuPDF extraction with span offsets
  citation_parser.py     — eyecite + resolve_citations()
  document_processor.py  — sync orchestrator (parse → store → link)
  async_processor.py     — asyncio.to_thread wrapper for ARQ
  workers.py             — process_pdf_job, embed_document_job, …
  embeddings.py          — sentence-transformers + pgvector queries
  llm_resolver.py        — Anthropic tie-break (feature-gated)
  courtlistener.py       — API client for enrichment + seed
  schemas.py             — Pydantic response shapes
  exceptions.py          — Structured error responses

alembic/versions/
  0001_initial_schema.py
  0002_pgvector_and_similarity.py
  0003_hnsw_index.py

scripts/
  seed.py                — pull N opinions from CourtListener
  reembed_corpus.py      — re-embed every doc with current model
  health_check.py        — local-dev sanity check
  start_backend.py       — non-Docker dev launcher
  run_test_suite.py      — pytest runner with categories
  deploy.{sh,ps1}        — Linux + Windows deploy helpers
  test-docker.sh         — Docker stack smoke test

frontend/
  src/app/
    page.tsx             — / dashboard
    graph/page.tsx       — /graph (the core canvas)
    documents/page.tsx   — /documents (corpus dashboard)
    documents/[id]/      — redirect to /graph?focus={id}
    upload/page.tsx      — redirect to /documents?upload=1
  src/components/
    CitationGraph.tsx    — Sigma canvas + EffectsReducer
    shell/               — AppShell, TopBar, LeftRail, InspectorPanel
    primitives/          — ConfidenceBadge, CitationText, CourtPill,
                           StatTile, EmptyState, Disclosure,
                           CitationSparkline, CommandPalette,
                           KeyboardShortcuts, ConfidenceBreakdown,
                           CitationListByPage
    upload/              — UploadModal, GlobalDropOverlay
    graph/               — TimelineScrubber
    ui/                  — shadcn primitives (button, dialog, etc.)
  src/lib/
    api.ts               — axios clients + types
    graph-data.ts        — buildSigmaGraph + Louvain + layout pipeline
    format.ts            — formatCaseTitle, formatRelativeDate, formatCourtShort
    inspector-store.ts   — what's in the right panel
    graph-store.ts       — focus, pulse, trail, constellation, search-pulse, year-range, spawn
    upload-store.ts      — upload queue + modal toggle
    confidence.ts        — tier mapping
    court.ts             — heuristic court classifier

tests/                   — pytest suite (unit + integration + smoke)
docker-compose.yml       — production stack (with nginx)
docker-compose.dev.yml   — dev stack (no nginx, hot-reload backend, bind-mounted source)
Dockerfile               — backend + worker image (pre-warms both ML models)
frontend/Dockerfile      — production multi-stage (npm ci + standalone)
frontend/Dockerfile.dev  — dev image (npm install + next dev)
Makefile                 — make up / seed / rebuild / reset / etc.
README.md                — quick start
AUDIT.md                 — this file
```

---

## 4. Backend API surface

### `/v1/*` — versioned, stable shapes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | DB + Redis connectivity, returns `{status, checks}` |
| GET | `/v1/documents` | List with `skip`/`limit` |
| GET | `/v1/documents/{id}` | Document + its citations array |
| GET | `/v1/documents/{id}/status` | `pending` / `processing` / `completed` / `failed` |
| GET | `/v1/documents/{id}/pdf` | Stream the PDF |
| GET | `/v1/documents/{id}/summary` | First ~480 char snippet of `full_text` |
| GET | `/v1/documents/{id}/full-text` | Entire extracted body text |
| GET | `/v1/documents/{id}/cites-out` | Outgoing citations (paginated) |
| GET | `/v1/documents/{id}/cited-by` | Reverse citations (paginated) |
| GET | `/v1/graph` | Citation graph for the corpus, with `min_confidence`, `court`, `year_min/max` filters |
| GET | `/v1/stats` | Aggregate counts + resolution rate + avg confidence |
| POST | `/v1/ingest` | Multipart PDF upload; enqueues processing |
| POST | `/v1/process` | Re-process all unprocessed documents |
| POST | `/v1/process/{id}` | Re-process one document |

### `/api/*` — semantic features (newer, separate prefix)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/similar/{doc_id}` | Top-k pre-computed semantic neighbours |
| GET | `/api/similar-edges` | All similarity edges above a floor (graph rendering) |
| POST | `/api/search` | Bi-encoder retrieval → cross-encoder re-rank |

`/api/search` returns an `X-Search-Mode: biencoder|crossencoder` header
so clients can show the user which path produced the ranking.

---

## 5. Data model

```sql
-- documents (one row per ingested opinion)
id UUID PK
title text
fingerprint text UNIQUE      -- sha256 of body text; idempotency key
source_path text             -- absolute path to PDF on disk
source_url text              -- e.g. CourtListener absolute_url
court text
year int
docket text
full_text text               -- extracted body, used for embedding + summary
embedding vector(768)        -- mpnet output, mean-pooled across chunks
embedded_at timestamp
created_at timestamp

-- citations (one row per eyecite hit, even shorts/supras/ids)
id UUID PK
from_doc_id FK → documents.id
to_doc_id FK → documents.id NULL   -- null = unresolved
raw_text text
normalized_key text                 -- "U.S._410_113_1973"
reporter, volume, page, year
page_number, span_start, span_end   -- where in the source PDF
citation_type text                  -- full | short | supra | id
confidence float
resolution_notes text               -- JSON array of strings
confidence_breakdown JSONB          -- {eyecite_base: 0.85, match_boost: 0.15, …}

-- semantic_similarity (pre-computed top-K neighbours, written symmetrically)
id UUID PK
source_id FK → documents.id ON DELETE CASCADE
target_id FK → documents.id ON DELETE CASCADE
similarity_score float CHECK 0..1
created_at timestamp
UNIQUE (source_id, target_id)
CHECK (source_id <> target_id)
```

**Indexes**

- `documents.embedding` — HNSW with `vector_cosine_ops`, `m=16, ef_construction=64`
- `citations.normalized_key`, `citations.from_doc_id`, `citations.to_doc_id`, `(reporter, volume, page)`
- `semantic_similarity.source_id`, `target_id`, and `(source_id, similarity_score DESC)`

---

## 6. Processing pipeline (per document)

```
upload → POST /v1/ingest
  ↓ (writes PDF + Document row)
ARQ.process_pdf_job
  ↓ DocumentProcessor.process_document()
  PDF → PyMuPDF → text + page spans
  citation_parser → eyecite.get_citations + resolve_citations
  short/supra/id forms inherit reporter/volume/page from full parent
  store rows in `citations` table with confidence_breakdown
  document_processor._link_citations:
    Stage 1: exact (reporter, volume, page) match → single doc → link
    Stage 2: ambiguous → narrow by year
    Stage 3 (if FEATURE_LLM_RESOLVER): Anthropic tie-break
  ↓ chains
ARQ.embed_document_job
  load doc.full_text
  chunk by tokens (380 wide, 60 overlap)
  embed each chunk → mean-pool → renormalize → store as vector(768)
  recompute top-K semantic neighbours via pgvector cosine_distance
  upsert symmetric rows into semantic_similarity
  ↓ optionally chains
ARQ.enrich_document_job (only if FEATURE_EXTERNAL_ENRICHMENT)
  pick first FullCaseCitation in the doc
  CourtListener lookup → backfill court / year / docket
```

The whole chain is idempotent — running `process_pdf_job(id)` twice
produces the same end state.

---

## 7. Frontend architecture

### State stores

Three Zustand stores. Each has a single responsibility.

**`inspector-store`** — what's in the right panel.

```ts
{ open, target: { kind: 'document' | 'citation' | 'similarity' | 'edge', ... } }
```

**`graph-store`** — every cross-component thing the canvas needs to know.

| Slice | Set by | Effect |
| --- | --- | --- |
| `focusedNodeIds` + `focusToken` | inspector "Center here", search select | `CameraFocus` two-phase animate (overshoot + settle) |
| `highlightedNodeId` + `pulseToken` | `pulse(id)` | 1.5 s amber pulse via `EffectsReducer.nodeReducer` |
| `trail: [{id, t}]` | auto on every `pulse()` | `SessionTrailOverlay` SVG polyline |
| `constellationFocus` | inspector "Constellation view" button | `EffectsReducer` recedes non-neighbours |
| `searchPulseIds: Set` | `TopBar` SearchCombobox on each result | live amber tint as user types |
| `yearRange` | `TimelineScrubber` | dim nodes outside the year window |
| `spawnIds: Map<id, startedAt>` | `UploadOrchestrator` on Case-ready | scale 0→1 grow-in over 700 ms |

**`upload-store`** — multi-file queue + modal toggle.

### Reducer architecture (the canvas)

Sigma allows exactly one `nodeReducer` and one `edgeReducer`. All
visual effects funnel through `EffectsReducer` in `CitationGraph.tsx`,
layered in this priority (later beats earlier):

```
year filter → constellation dim → hover dim → search-pulse tint →
spawn grow-in → pulse amber → breathing
```

A `useRef` phase + rAF loop powers continuous animations (breathing,
search pulse, spawn). The loop only runs when at least one continuous
source is active. It runs at 30 fps for ambient-only animation, 60 fps
when spawn or search-pulse is active. Pauses on `document.hidden`.
Skipped entirely under `prefers-reduced-motion`.

### Routes

| Route | Purpose |
| --- | --- |
| `/` | Dashboard — stats, top central cases, recent uploads |
| `/graph` | The core canvas. Accepts `?q=…` (semantic search) and `?focus={id}` (deep link to a case) |
| `/documents` | Sortable corpus dashboard with stats bar + per-row sparklines. `?upload=1` auto-opens the upload modal |
| `/documents/[id]` | Redirects to `/graph?focus={id}` (preserved for old links) |
| `/upload` | Redirects to `/documents?upload=1` |

### Layout shell

`AppShell` wraps every page with: `LeftRail` (220 px nav) | `TopBar`
(48 px breadcrumbs + global semantic search + theme toggle) | `main`
(page content) | `InspectorPanel` (380 px right rail). Layout is fixed
height `h-screen`; the canvas/page area scrolls.

`UploadModal` and `GlobalDropOverlay` are mounted at the shell level so
any page can open the modal and any drop anywhere on the app accepts a
file.

---

## 8. Graph visualisation (the deep dive)

### Build pipeline (`graph-data.ts::buildSigmaGraph`)

```
1. add nodes (placeholder colour = court tone, size = 6)
2. add citation edges (weight = 1 + confidence)
3. add ALL semantic edges above the fetch floor (weight = 0.5 × similarity)
4. louvain.assign() with edge `weight` → each node gets a community index
5. recompute size from sqrt(in_degree + 0.4 × out_degree)
   recolour from COMMUNITY_COLORS[community % 12], shade ±12 luminance by year
6. layout pipeline (see below)
```

### Layout pipeline (`graph-data.ts::runLayout`)

```
random.assign(graph, scale)        — for graphs > 8 nodes
circular.assign(graph, 80)         — for ≤8 nodes (ring reads better)
forceAtlas2.assign with:
  - inferred settings as base
  - adjustSizes: true              — respects per-node radius
  - barnesHutOptimize: n > 80      — O(n log n)
  - scalingRatio: 14 (n≥200) else inferred
  - slowDown: 5
  - edgeWeightInfluence: 1
  - iterations: 120 / 180 / 240 / 320 by node count
noverlap.assign with:
  - margin: 8 (n≥200) else 5
  - maxIterations: 50 / 80 by node count
```

### Visual encoding

| Channel | Encodes | Where it lives |
| --- | --- | --- |
| Node colour | Louvain community membership | `COMMUNITY_COLORS[12]` |
| Node luminance | Filing year (older→darker, newer→lighter) | `shadeByYear()` ±12 RGB |
| Node size | Citation degree, sqrt-scaled | `nodeSizeRange(n)` density-aware |
| Edge colour (citation) | Confidence tier (high/medium/low/unresolved) | `TIER_COLORS` |
| Edge colour (semantic) | Emerald @ 70% alpha | `SEMANTIC_EDGE_COLOR` |
| Edge type | Citation: arrow · Semantic: line | Sigma built-ins |
| Edge size (citation) | 2.5 + confidence × 2 | inline |
| Edge size (semantic) | 1.5 + similarity × 2 | inline |
| Threshold fade | Continuous α across ±0.05 window | `EffectsReducer.edgeReducer` |
| Hover dim | Non-neighbours fade to slate-300, no label | `EffectsReducer.nodeReducer/edgeReducer` |
| Constellation dim | Non-focus recedes to slate-200 + 25% size | same |
| Pulse | Amber + 1.8× size, 1.5 s | same |
| Spawn | Scale 0→1 over 700 ms, amber tint <70% | same |
| Search pulse | Amber tint + slight grow on matching nodes | same |
| Breathing | Top-3 by degree, 6% size sine on a 1.5 s period | same |
| Year filter | Outside-range nodes dim to slate-300 | same |

### Density-aware sizing

| Corpus size | Min size | Max size | Label render threshold |
| --- | --- | --- | --- |
| <60 | 8 | 26 | 5 |
| 60–99 | 6 | 22 | 5 |
| 100–199 | 4 | 18 | 8 |
| ≥200 | 3 | 14 | 12 |

Below the label render threshold, labels never appear statically. Hover
forces a label on via `forceLabel: true` regardless of size.

### Camera behaviour

- Initial mount: zooms to fit the top-3 most-cited landmarks (gives the
  user something to orient around instead of a full-graph zoom-out).
- "Fit view" button (top-right): `camera.animatedReset({duration: 400})`.
- Pulse: two-phase animate — zoom past the target (`ratio: 0.32`,
  350 ms) then settle back (`ratio: 0.4`, 200 ms). Feels physical.
- Constellation enter: fits the focus + neighbours (`ratio: 0.25`,
  600 ms). Exit: `animatedReset` to full graph.
- Camera focus from search hit: `setFocus(ids)` → camera animates to
  centroid; pulse() additionally pulses one specific node.

### Performance discipline

- **Build is synchronous** but tuned: 100-node corpus lays out in ~80 ms,
  500 nodes in ~500 ms. No web worker.
- **Threshold drag does NOT rebuild the graph**. The threshold is read
  by the `edgeReducer` and applied as a continuous opacity ramp, so a
  slider drag is just a render reflow.
- **Similarity-edge fetch is threshold-aware** — fetches edges ≥
  `threshold − 0.15`, capped at 800. Default threshold 0.85 → ~150
  edges instead of 2000.
- **rAF loop only runs** when at least one continuous animation is
  active (breathing, search pulse, spawn). Caps at 30 fps for ambient
  only; 60 fps when spawn / search-pulse is active. Pauses on
  `document.hidden`.
- **`hideEdgesOnMove` + `hideLabelsOnMove`** — Sigma hides edges and
  labels mid-pan/zoom; redraws on settle. ~3× smoother gesture feel
  at 200+ nodes.
- **`barnesHutOptimize` flips on at n > 80** (was n > 200) — O(n log n)
  repulsion for medium graphs.
- **`CitationSparkline` is `React.memo`'d** — 100 row sparklines no
  longer re-render on every sort/filter keystroke.

---

## 9. Diagnostic checklist — when something feels broken

### Visual / layout

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Vertical arc of nodes on left edge of graph | `circular()` initial layout that FA2 didn't disperse | Already switched to `random()` for n>8 — if it returns, raise FA2 iteration count |
| Two visible nodes overlap | `adjustSizes` missing OR `noverlap` margin too small | Verify `runLayout` in `graph-data.ts` |
| Hairball at the centre | Too many edges visible | Raise `DEFAULT_THRESHOLD` (currently 0.85) or implement a min-degree filter |
| Floating disconnected nodes | Doc has zero linked citations and zero semantic neighbours | Re-embed (`make reembed`), or check citation linking |
| Communities all same colour | Louvain failed silently | Check `graph.size > 0` before expecting communities |
| Labels overlap | `labelGridCellSize` too small | Raise to 150+ |
| Labels on every tiny node | `labelRenderedSizeThreshold` too low | Raise per density bracket |
| Long court name wraps to multiple lines | `whitespace-nowrap` missing on pill | Verified fixed in `CourtPill` |
| `seed_X__Y_HASH` in titles | Doc title fallback leaked | `formatCaseTitle()` strips it; verify it's applied at the display site |
| Dates render as "4/29/2026" | Raw `toLocaleDateString` | Use `formatRelativeDate` from `lib/format.ts` |

### Performance

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Initial graph paint feels slow (≥1 s) | FA2 iteration count too high for the corpus size | Drop iterations in `runLayout`'s switch |
| Hover feels laggy | `setSettings` rebinding nodeReducer too often | The reducer is set once per static-state change; check what's changing |
| Threshold drag is choppy | Graph rebuilds on threshold change | Threshold is render-time only — verify `useMemo` deps don't include `semanticThreshold` |
| Background tab burns CPU | rAF loop running on hidden tab | Already gated by `document.hidden` |
| Sparklines re-render on keystroke | `CitationSparkline` not memoised | Already `React.memo` — verify the import is the memo'd export |
| Search request fires on every keystroke | Debounce missing | TopBar SearchCombobox debounces 300 ms |
| Layout takes > 1s on 500 nodes | Single-threaded by design | Future: move to `graphology-layout-forceatlas2/worker` |

### Data / pipeline

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Most citations show 0 / 0 cited-by | Citation linking rate low (corpus doesn't contain the cited cases) | Seed deeper / older corpus |
| Search returns nothing for proper noun | Bi-encoder embeds short queries poorly | Future: hybrid lexical + semantic retrieval |
| Embedding worker stuck on long doc | `_MAX_CHARS` truncation may be hitting | Check token chunk count in worker logs |
| Worker fails with "no such table" | Migrations not run | `make migrate` |
| Worker fails with NumPy ABI warning | numpy 2.x + torch 2.2 mismatch | numpy is pinned to 1.26.4 in `requirements.txt` — rebuild |
| Worker stuck on Case ready | Polling /status returns 'processing' | Check ARQ queue depth in Redis |
| `down -v` wipes corpus | Anonymous volumes removed | Use `down` (no -v) to preserve, or `make rebuild-frontend` for fe-only |

### Docker

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Module not found` on a frontend dep that's in package.json | Anonymous `node_modules` volume cached an old install | `make rebuild-frontend` |
| Backend boots but `/v1/*` 500s with `RelatedCase is not defined` | Forward-ref string in `response_model` | Use `list[RelatedCase]` not `list["RelatedCase"]` |
| CourtListener returns `unknown_params=["ordering"]` | Param renamed | Use `order_by` not `ordering` (v4 API) |
| Topic with spaces fails | URL not encoded | Pass via `client.get(params=...)` not string concat |
| Frontend shows old code despite source change | Anonymous volume vs bind mount mismatch | `down -v` or `make rebuild-frontend` |

---

## 10. Tuning knobs

### Backend

| Knob | File | Default | Effect |
| --- | --- | --- | --- |
| `EMBEDDING_MODEL` | `.env` / `config.py` | `all-mpnet-base-v2` | Bi-encoder model name |
| `EMBEDDING_DIM` | same | 768 | Vector column width |
| `EMBEDDING_TOP_K` | same | 25 | Pre-computed neighbours per doc |
| `SIMILARITY_THRESHOLD_DEFAULT` | same | 0.75 | Backend graph default (frontend overrides to 0.85) |
| `FEATURE_EMBEDDINGS` | same | true | Toggle embedding pipeline |
| `FEATURE_CROSS_ENCODER` | same | true | Re-rank /api/search results |
| `CROSS_ENCODER_MODEL` | same | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Re-ranker model |
| `SEARCH_CANDIDATE_POOL` | same | 20 | Bi-encoder retrieves N → cross-encoder re-ranks |
| `FEATURE_LLM_RESOLVER` | same | true | Anthropic tie-break for ambiguous citations |
| `LLM_MODEL` | same | `claude-opus-4-7` | Anthropic model |
| `MIN_CONFIDENCE_DEFAULT` | same | 0.7 | /v1/graph default min_confidence filter |
| `FEATURE_EXTERNAL_ENRICHMENT` | same | false | CourtListener metadata backfill |
| `COURTLISTENER_API_KEY` | same | "" | Higher rate limits when set |

### Frontend graph

| Knob | File | Default | Effect |
| --- | --- | --- | --- |
| `DEFAULT_THRESHOLD` | `app/graph/page.tsx` | 0.85 | Initial similarity slider position |
| `FALLBACK_THRESHOLD` | same | 0.7 | What "lower threshold" hint sets |
| Similarity-edge fetch floor | `CitationGraph.tsx` | `threshold - 0.15`, min 0.5 | What `getSimilarityEdges` requests |
| Similarity-edge fetch limit | same | 800 | Cap on fetch |
| `THRESHOLD_FADE_WINDOW` | same | 0.05 | Soft-fade range around threshold |
| `BREATHING_LANDMARKS` | same | 3 | How many landmarks pulse continuously |
| `PULSE_MS` | `graph-store.ts` | 1500 | Pulse animation duration |
| `TRAIL_MAX` | same | 8 | Session trail length cap |
| `SPAWN_MS` | same | 700 | New-doc grow-in duration |
| FA2 iterations | `graph-data.ts::runLayout` | 120/180/240/320 | By node count brackets |
| `barnesHutOptimize` threshold | same | n > 80 | When to flip on the O(n log n) repulsion |
| `noverlap` margin/iterations | same | 5–8 / 50–80 | Adjacent-node spacing + iteration cap |
| `COMMUNITY_COLORS` | `graph-data.ts` | 12-tone palette | Louvain community colours |
| Citation count "average" | inspector `Section.spark` | 8 cites, 4 cited-by | Visual baseline for "is this a hub?" |
| Court shorthand map | `format.ts` `COURT_SHORTHAND` | SCOTUS / 9th Circuit / etc. | Long → short rendering |

### Frontend animation

| Knob | File | Default | Effect |
| --- | --- | --- | --- |
| Inspector reveal stagger | `InspectorPanel.tsx` `Reveal` | 40 ms per section | Top-down cascade timing |
| Camera overshoot ratio | `CitationGraph.tsx` `CameraFocus` | 0.32 first, 0.4 settle | Pulse zoom intensity |
| Constellation camera ratio | `CitationGraph.tsx` `ConstellationCamera` | 0.25 | How tight the focus zooms |
| Trail polyline alpha | `SessionTrailOverlay` SVG | 0.45 | How prominent the path is |

---

## 11. Operations

### Local development

```bash
make up           # bring up the dev stack
make seed         # 200 SCOTUS opinions from CourtListener
make logs-worker  # follow PDF parse / embed jobs
make psql         # open psql on the dev DB
make test         # pytest inside backend container
```

`make` with no args lists every target. The Makefile wraps
`docker compose -f docker-compose.dev.yml ...` so the file flag isn't
in muscle memory.

### Reset workflows

| What you want | Command |
| --- | --- |
| Stop everything (preserves db + corpus) | `make down` |
| Wipe everything (asks for y/N) | `make reset` or `make clean` |
| Wipe + re-seed in one go | `make reseed` |
| Rebuild backend + worker only | `make rebuild` |
| Rebuild frontend after package.json change | `make rebuild-frontend` |
| Rebuild every image (preserves db) | `make rebuild-all` |
| Re-embed every doc with current model | `make reembed` |

### Environment variables

`.env` (cp from `env.example`) holds:

```
DATABASE_URL=postgresql+asyncpg://citations:citations@localhost:5432/citations
DATABASE_URL_SYNC=postgresql+psycopg2://citations:citations@localhost:5432/citations
PDF_STORAGE_PATH=./data/pdfs
REDIS_URL=redis://localhost:6379

ANTHROPIC_API_KEY=
LLM_MODEL=claude-opus-4-7
FEATURE_LLM_RESOLVER=true

FEATURE_EXTERNAL_ENRICHMENT=false
COURTLISTENER_API_KEY=

MIN_CONFIDENCE_DEFAULT=0.7

FEATURE_EMBEDDINGS=true
EMBEDDING_MODEL=all-mpnet-base-v2
EMBEDDING_DIM=768
EMBEDDING_TOP_K=25
SIMILARITY_THRESHOLD_DEFAULT=0.75

FEATURE_CROSS_ENCODER=true
CROSS_ENCODER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
SEARCH_CANDIDATE_POOL=20

LOG_LEVEL=INFO
```

### Performance baseline (verified via Playwright on 100-doc corpus)

| Metric | Value |
| --- | --- |
| Idle FPS on /graph | 59–60 |
| FPS during canvas hover (2 s sample) | avg 59, p95 frame 17 ms, max-frame outlier 50 ms |
| DOMContentLoaded on /graph | 199 ms |
| First Contentful Paint | 224 ms |
| First-load JS transfer | ~7 KB (HTML; chunks lazy-load) |
| Initial graph layout time (100 nodes) | ~80 ms |
| Initial graph layout time (estimated, 500 nodes) | ~500 ms |
| Memory footprint | 55 MB JS heap |

---

## 12. Hard constraints

These are non-negotiable design rules. Every change must respect them.

- **Local-first.** No cloud DB, no managed embedding service, no
  external API for inference. CourtListener and Anthropic are *optional*
  feature-gated integrations.
- **Docker Compose is the single deployment surface.** Anything that
  needs to run outside containers isn't in scope.
- **SQLAlchemy is the ORM.** No raw SQL outside Alembic migrations and
  the pgvector index DDL.
- **`/v1/*` response shapes never change.** Adding new fields is OK
  (additive); removing or renaming is not. New endpoints can land on
  `/v1/*` or `/api/*` freely.
- **Migrations are additive.** No `drop_all`/`create_all` in production
  paths. Schema evolves through Alembic revisions.
- **Dark mode at parity.** Every new component renders correctly in
  both themes. No exceptions.
- **`prefers-reduced-motion` is honoured.** Every keyframe animation is
  wrapped in `motion-safe:` or gated by `matchMedia`.
- **No new npm dependencies** unless they're tightly scoped (one piece
  of work, single library) and the existing toolkit can't do it. The
  graphology family is the bar — purpose-built, single-use, small.
- **No backend changes for frontend-only work.** Backend additions go
  through their own review.

---

## 13. Known gaps and deferred work

These are real product concerns currently parked. None are blockers
for the existing user flow; all are improvements.

| Area | Issue | Path forward |
| --- | --- | --- |
| Citation linking | ~9% link rate on a SCOTUS-only corpus — most extracted citations point at cases not in the local corpus | Seed deeper / older landmarks (Marbury, Brown, Roe), OR add CourtListener-side fuzzy resolution |
| Search | Bi-encoder returns nothing for proper-noun queries ("Riley" → 0 hits) | Hybrid retrieval: fall back to `title ILIKE %q%` when bi-encoder yields nothing above threshold |
| Date range | Corpus spans 2024–2026 only (CourtListener default ordering) | Seed with `--ordering=cluster__date_filed` to spread across decades |
| Custom dashed edge program | The WebGL `DashedEdgeProgram` in `lib/sigma-dashed-edge.ts` has a constructor signature mismatch with @react-sigma 3.4; semantic edges currently render as solid `'line'` with translucent emerald | Update super() call to match Sigma 2.4's `AbstractEdgeProgram` constructor (drop the `renderer` 6th arg; pass a `bindLocations` callback instead) |
| Web-worker layout | All FA2 + Louvain + noverlap on the main thread | `graphology-layout-forceatlas2/worker` for >300-node corpora |
| Animated row reorder | Documents sort changes are instant (no layout animation) | Would require `framer-motion`; deliberately skipped |
| Mobile / touch | Desktop-only by design; no touch gestures on Sigma canvas | Out of scope per the original design brief |

---

## 14. Where this came from (brief history)

For context, the product evolved through several distinct phases on
the `dev` branch. Older details are in git history; this file is the
canonical current-state reference.

1. **Initial migration**: SQLite + pdfplumber + custom regex extraction
   → Postgres + pgvector + PyMuPDF + eyecite.
2. **Embedding pipeline**: chunked + mean-pooled mpnet, ARQ-driven
   `embed_document_job`.
3. **Cross-encoder re-ranking**: `ms-marco-MiniLM-L-6-v2` as a second
   stage on `/api/search`.
4. **Sigma.js + Graphology**: replaced React Flow with WebGL renderer.
5. **Frontend UX overhaul**: shadcn/ui shell, inspector, search dropdown,
   upload modal, empty states.
6. **Living-surface pass**: hover-highlight, constellation view,
   session trail, breathing landmarks, smooth threshold fade, timeline
   scrubber, documents dashboard with sparklines.
7. **Polish + perf pass**: Louvain communities, density-aware sizing,
   format helpers (case titles, dates, court names), threshold-aware
   edge fetch, rAF cap, layout pipeline tuning.

Each pass was additive; no functionality has been removed.
