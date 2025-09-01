# Resolver Policy (AI Context)

Decision order:
1) Exact match on (reporter, volume, page) with plausible year → accept without LLM.
2) If multiple exacts: prefer same jurisdiction/court if known; else prefer candidate with matching case name (string similarity).
3) If still tied: call LLM with compact candidate list and require JSON selection per /cursor/ai/llm.contract.md.

Prohibitions:
- Do not invent case names or years.
- Do not modify deterministic matches.
- Return null when insufficient certainty (confidence < 0.5) and let human review.
