# Data Models (logical)

Document:
- id (UUID), title, fingerprint (hash), source_path/URL
- court?, year?, docket?
- created_at

Citation:
- id (UUID), from_doc_id (UUID), to_doc_id? (UUID)
- raw_text, normalized_key
- reporter, volume, page, year?
- page_number?, span_start?, span_end?
- confidence (0..1), resolution_notes [string]

Graph:
- nodes: [{id,label,meta}]
- edges: [{id,source,target,confidence}]
