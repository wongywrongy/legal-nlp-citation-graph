# API Contract (excerpt)

GET /v1/documents
→ 200 { items: Document[], total: number }

GET /v1/documents/{id}
→ 200 { document: Document, citations: Citation[] }

GET /v1/documents/{id}/pdf
→ Streams the PDF bytes

GET /v1/graph?min_confidence=0.7
→ 200 { nodes: GraphNode[], edges: GraphEdge[] }

POST /v1/ingest
form-data: files[]
→ 202 { document_ids: string[] }
