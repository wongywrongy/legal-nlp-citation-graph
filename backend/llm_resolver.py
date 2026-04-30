"""
LLM-assisted citation resolver.

Used only when deterministic matching yields multiple candidates. Follows the
JSON contract in cursor/ai/llm.contract.md and the policy in
cursor/ai/resolver.policy.md.

Two entry points:
  - resolve_ambiguous_citation       : async, used inside async pipelines
  - resolve_ambiguous_citation_sync  : sync wrapper used by the legacy
    DocumentProcessor.process_document path

Returns None (and logs at INFO) when the resolver is disabled or no API key
is configured — the caller is expected to leave the citation unresolved.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Iterable, Optional

import structlog

from backend.config import settings

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You are a legal citation resolver. You receive a citation and a list of "
    "candidate documents. Return ONLY valid JSON with these keys:\n"
    "  best_document_id (string or null),\n"
    "  normalized_key (string),\n"
    "  confidence (number between 0.0 and 1.0),\n"
    "  notes (array of short strings explaining your reasoning).\n"
    "Never invent case names, reporters, or years. If your confidence is "
    "below 0.5, set best_document_id to null."
)


def _payload(citation, candidates: Iterable) -> dict:
    return {
        "raw_citation": citation.raw_text,
        "normalized": {
            "reporter": citation.reporter,
            "volume": citation.volume,
            "page": citation.page,
            "year": citation.year,
        },
        "candidates": [
            {
                "document_id": c.id,
                "title": c.title,
                "court": c.court,
                "year": c.year,
                "docket": c.docket,
            }
            for c in candidates
        ],
    }


async def resolve_ambiguous_citation(citation, candidates) -> Optional[dict]:
    if not settings.feature_llm_resolver:
        logger.info("LLM resolver disabled by feature flag")
        return None
    if not settings.anthropic_api_key:
        logger.info("LLM resolver skipped — ANTHROPIC_API_KEY not set")
        return None

    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        logger.warning("anthropic SDK not installed; skipping LLM resolution")
        return None

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_payload = _payload(citation, candidates)

    try:
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(user_payload)}],
        )
    except Exception as e:
        logger.warning("LLM call failed", error=str(e))
        return None

    text = _extract_text(response)
    parsed = _safe_parse_json(text)
    if parsed is None:
        logger.warning("LLM returned non-JSON output", raw=text[:300])
        return None

    logger.info(
        "LLM resolver result",
        citation_key=citation.normalized_key,
        chosen=parsed.get("best_document_id"),
        confidence=parsed.get("confidence"),
    )
    return parsed


def resolve_ambiguous_citation_sync(citation, candidates) -> Optional[dict]:
    """Run the async resolver from a sync context. Safe to call when no event
    loop is running (the legacy DocumentProcessor path)."""
    try:
        return asyncio.run(resolve_ambiguous_citation(citation, candidates))
    except RuntimeError:
        # Already inside a loop — fall back to no-op rather than nesting loops.
        logger.warning("Refusing to nest event loops; returning None")
        return None


def _extract_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if not content:
        return ""
    first = content[0]
    return getattr(first, "text", "") or ""


def _safe_parse_json(text: str) -> Optional[dict]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Strip code fences if the model wrapped the JSON.
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[-1] if "\n" in text else text
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return None
    return None
