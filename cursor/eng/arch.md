# Architecture

- Parsing Service (Python): PDF text → eyecite → normalized citations → candidate linking → (optional) LLM tie-breaker → DB.
- Storage: metadata + edges in relational DB; PDFs on disk/S3.
- API Service: REST endpoints for ingest, documents, graph.
- Frontend: Next.js + React Flow + PDF.js viewer.

Use eyecite as the single source of truth for citation extraction/normalization.
