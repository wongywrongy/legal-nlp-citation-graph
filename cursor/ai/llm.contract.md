# LLM Contract (Strict JSON Only)

INPUT (example):
{
  "raw_citation": "123 Cal. 456 (1998)",
  "normalized": {"reporter":"Cal.","volume":123,"page":456,"year":1998,"case_name":null},
  "candidates": [
    {"document_id":"DOC-1","title":"People v. Roe","reporter":"Cal.","volume":123,"page":456,"year":1998,"court":"Cal. Sup. Ct."},
    {"document_id":"DOC-2","title":"Roe v. People","reporter":"Cal.","volume":123,"page":456,"year":1999,"court":"Cal. App."}
  ]
}

OUTPUT (must be valid JSON, no prose):
{
  "best_document_id": "DOC-1",
  "normalized_key": "Cal._123_456_1998",
  "confidence": 0.86,
  "notes": [
    "Exact reporter/vol/page match",
    "Year matches candidate DOC-1",
    "Title similarity slightly favors DOC-1"
  ]
}
