"""Tests für den Keyword-Generator (AP-6.1c). Alle LLM-Aufrufe sind gemockt."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.index.keyword_generator import (
    _append_cache_entry,
    _load_cache,
    _validate_keywords,
    enrich_with_keywords,
)


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _make_chunk(chunk_id: str = "forum__post_001", text: str = "Text.") -> dict:
    return {"id": chunk_id, "text": text, "metadata": {}}


def _good_keywords(n: int = 5) -> list[str]:
    return [f"Schlüsselwort{i}" for i in range(n)]


# ── Validierung (3 Tests) ────────────────────────────────────────────────────


def test_validate_keywords_filters_short() -> None:
    result = _validate_keywords(["a", "ab", "abc"])
    # "a" is 1 char → filtered; "ab" is 2 chars → valid; "abc" valid
    assert "a" not in result
    assert "ab" in result
    assert "abc" in result


def test_validate_keywords_filters_long() -> None:
    too_long = "x" * 61
    valid = "Auftrag"
    result = _validate_keywords([too_long, valid])
    assert too_long not in result
    assert valid in result


def test_validate_keywords_keeps_valid() -> None:
    kws = ["MWST", "Mehrwertsteuer", "Auftrag", "Rechnungsversand"]
    result = _validate_keywords(kws)
    assert result == kws


# ── Caching (3 Tests) ────────────────────────────────────────────────────────


def test_load_cache_empty_file(tmp_path: Path) -> None:
    assert _load_cache(tmp_path / "missing.jsonl") == {}


def test_append_cache_entry_writes_jsonl(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.jsonl"
    _append_cache_entry(cache_path, "c1", ["MWST", "Auftrag"])

    lines = cache_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["chunk_id"] == "c1"
    assert entry["keywords"] == ["MWST", "Auftrag"]


def test_enrich_with_keywords_uses_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chunk im Cache → kein LLM-Call."""
    cache_path = tmp_path / "cache.jsonl"
    chunk_id = "forum__post_001"
    _append_cache_entry(cache_path, chunk_id, _good_keywords(6))

    call_count: dict[str, int] = {"n": 0}

    def _mock_call_llm(
        messages: list, schema: dict
    ) -> tuple[list[str], int, int]:
        call_count["n"] += 1
        return [], 0, 0

    monkeypatch.setattr(
        "rag.index.keyword_generator._call_llm", _mock_call_llm
    )

    chunks = [_make_chunk(chunk_id)]
    enrich_with_keywords(chunks, cache_path=cache_path)

    assert call_count["n"] == 0
    kws = chunks[0]["metadata"]["keywords"].split(",")
    assert len(kws) == 6


# ── Hauptfunktion mit Mock (2 Tests) ─────────────────────────────────────────


def test_enrich_with_keywords_aborts_on_low_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Alle Chunks erhalten <3 Keywords → RuntimeError."""

    def _mock_call_llm(
        messages: list, schema: dict
    ) -> tuple[list[str], int, int]:
        return ["ok", "ok"], 50, 10  # 2 valid keywords → below threshold

    monkeypatch.setattr(
        "rag.index.keyword_generator._call_llm", _mock_call_llm
    )

    chunks = [_make_chunk("forum__a"), _make_chunk("forum__b")]
    with pytest.raises(RuntimeError, match="Keyword-Rate"):
        enrich_with_keywords(chunks, cache_path=tmp_path / "c.jsonl")


def test_enrich_with_keywords_serializes_to_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mock liefert valide Keywords → Chunk hat kommagetrennten String."""
    keywords = ["MWST", "Auftrag", "Rechnungsversand", "Buchung", "Stammdaten"]

    def _mock_call_llm(
        messages: list, schema: dict
    ) -> tuple[list[str], int, int]:
        return keywords, 100, 30

    monkeypatch.setattr(
        "rag.index.keyword_generator._call_llm", _mock_call_llm
    )

    chunks = [_make_chunk("forum__serial")]
    enrich_with_keywords(chunks, cache_path=tmp_path / "c.jsonl")

    result = chunks[0]["metadata"]["keywords"]
    assert result == ",".join(keywords)
