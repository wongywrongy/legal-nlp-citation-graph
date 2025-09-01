# Dev & Ops

- Local storage: /data/pdfs
- Feature flags via env:
  - FEATURE_EXTERNAL_ENRICHMENT=false
  - MODEL_PROVIDER=openai|local
- Logging: structured JSON logs with trace IDs across ingestion→parsing→linking.
