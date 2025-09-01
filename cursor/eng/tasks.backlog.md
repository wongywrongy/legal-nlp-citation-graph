# Tasks Backlog (first vertical slice)

1. Bootstrap services and env files; no secrets in repo.
2. Implement ingestion: accept PDF, store file, compute fingerprint, create Document record.
3. Parsing: run eyecite on plain text; persist Citation rows with spans/pages and normalized key.
4. Candidate linking: match (reporter, volume, page), gate LLM to tie-break only.
5. Graph API: return nodes/edges with confidence and basic centrality.
6. Frontend pages: /upload → /graph → /documents/[docId].
7. Tests: unit tests for normalization/linking; golden set fixtures.
8. Optional: CourtListener lookup behind a feature flag.
