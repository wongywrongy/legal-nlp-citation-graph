# Testing Strategy

- Unit: extraction→normalization→linking (no network).
- Fixtures: 20 PDFs (or excerpts) with expected edges.
- Contract tests: API responses match schemas.
- LLM tests: freeze input/output JSON via snapshot; ensure deterministic behavior thresholds.
