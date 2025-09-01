# Extraction & Normalization Pipeline (AI Context)

Stages:
1) PDF Text: extract text with page numbers and spans (e.g., PyMuPDF). Include character offsets for each citation span.
2) Candidate Citations: use eyecite to parse citations and parallel cites; store raw text, normalized form, reporter, volume, page, year if available.
3) Canonical Key: Build (case_name?, reporter, volume, page, year?) normalized key. Prefer eyecite's normalization.
4) Deduplication: merge duplicates on the same page; keep highest-quality instance.
5) Link Candidates: If the repo already contains ingested docs, propose to_doc candidates by matching (reporter, volume, page), then constrain by year/court if present.
6) LLM Tie-break: Only when multiple candidates remain with near-equal scores. Provide structured decision.

Confidence:
- Start from exact-field match score.
- Penalize missing/contradictory fields.
- Add small bonus if model agrees with top deterministic match.
