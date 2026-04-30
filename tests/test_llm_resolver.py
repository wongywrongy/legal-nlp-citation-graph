"""
Tests for the LLM resolver. Network calls are not exercised — we verify the
payload contract and the JSON-parsing layer with hand-written fixtures.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend import llm_resolver


@pytest.mark.unit
@pytest.mark.fast
def test_payload_matches_contract():
    citation = SimpleNamespace(
        raw_text="410 U.S. 113 (1973)",
        reporter="U.S.",
        volume=410,
        page=113,
        year=1973,
    )
    candidates = [
        SimpleNamespace(id="DOC-1", title="Roe v. Wade", court="U.S.", year=1973, docket="70-18"),
        SimpleNamespace(id="DOC-2", title="Doe v. Bolton", court="U.S.", year=1973, docket="70-40"),
    ]
    payload = llm_resolver._payload(citation, candidates)
    assert payload["raw_citation"] == "410 U.S. 113 (1973)"
    assert payload["normalized"] == {"reporter": "U.S.", "volume": 410, "page": 113, "year": 1973}
    assert len(payload["candidates"]) == 2
    assert payload["candidates"][0]["document_id"] == "DOC-1"


@pytest.mark.unit
@pytest.mark.fast
def test_safe_parse_handles_plain_json():
    parsed = llm_resolver._safe_parse_json('{"best_document_id":"X","confidence":0.7}')
    assert parsed == {"best_document_id": "X", "confidence": 0.7}


@pytest.mark.unit
@pytest.mark.fast
def test_safe_parse_strips_code_fences():
    raw = '```json\n{"best_document_id":"X","confidence":0.7}\n```'
    parsed = llm_resolver._safe_parse_json(raw)
    assert parsed and parsed["best_document_id"] == "X"


@pytest.mark.unit
@pytest.mark.fast
def test_safe_parse_returns_none_on_garbage():
    assert llm_resolver._safe_parse_json("") is None
    assert llm_resolver._safe_parse_json("not json at all") is None


@pytest.mark.unit
@pytest.mark.fast
def test_resolver_short_circuits_when_disabled(monkeypatch):
    monkeypatch.setattr(llm_resolver.settings, "feature_llm_resolver", False)
    result = llm_resolver.resolve_ambiguous_citation_sync(
        SimpleNamespace(raw_text="x", reporter=None, volume=None, page=None, year=None, normalized_key="k"),
        [],
    )
    assert result is None


@pytest.mark.unit
@pytest.mark.fast
def test_resolver_short_circuits_without_api_key(monkeypatch):
    monkeypatch.setattr(llm_resolver.settings, "feature_llm_resolver", True)
    monkeypatch.setattr(llm_resolver.settings, "anthropic_api_key", "")
    result = llm_resolver.resolve_ambiguous_citation_sync(
        SimpleNamespace(raw_text="x", reporter=None, volume=None, page=None, year=None, normalized_key="k"),
        [],
    )
    assert result is None
