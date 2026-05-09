"""Tests für den LLM-Tagger (AP-6.1b). Kein echter API-Call — alle LLM-Aufrufe
werden via monkeypatch gemockt.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.index.llm_tagger import (
    _append_cache_entry,
    _load_cache,
    _validate_tags,
    tag_chunks,
)
from rag.index.tag_taxonomy import MAX_TAGS, MODULE_TAGS, THEMA_TAGS, TYP_TAGS


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _make_chunk(chunk_id: str = "forum__post_001", text: str = "Text.") -> dict:
    return {"id": chunk_id, "text": text, "metadata": {}}


def _valid_module() -> str:
    return next(iter(sorted(MODULE_TAGS)))


def _valid_thema() -> str:
    return next(iter(sorted(THEMA_TAGS)))


def _valid_typ() -> str:
    return next(iter(sorted(TYP_TAGS)))


# ── Validierung (3 Tests) ────────────────────────────────────────────────────


def test_validate_tags_filters_invalid() -> None:
    raw = {
        "module_tags": [_valid_module(), "UNGÜLTIG"],
        "thema_tags": ["NichtDrin", _valid_thema()],
        "typ_tags": [_valid_typ()],
    }
    result = _validate_tags(raw)
    assert result["module_tags"] == [_valid_module()]
    assert result["thema_tags"] == [_valid_thema()]
    assert result["typ_tags"] == [_valid_typ()]


def test_validate_tags_applies_max_limits() -> None:
    many_modules = sorted(MODULE_TAGS)[: MAX_TAGS["module_tags"] + 2]
    many_thema = sorted(THEMA_TAGS)[: MAX_TAGS["thema_tags"] + 2]
    many_typ = sorted(TYP_TAGS)[: MAX_TAGS["typ_tags"] + 1]
    raw = {
        "module_tags": many_modules,
        "thema_tags": many_thema,
        "typ_tags": many_typ,
    }
    result = _validate_tags(raw)
    assert len(result["module_tags"]) == MAX_TAGS["module_tags"]
    assert len(result["thema_tags"]) == MAX_TAGS["thema_tags"]
    assert len(result["typ_tags"]) == MAX_TAGS["typ_tags"]


def test_validate_tags_empty_categories() -> None:
    result = _validate_tags({})
    assert result["module_tags"] == []
    assert result["thema_tags"] == []
    assert result["typ_tags"] == []


# ── Caching (3 Tests) ────────────────────────────────────────────────────────


def test_load_cache_empty_file(tmp_path: Path) -> None:
    missing = tmp_path / "no_cache.jsonl"
    assert _load_cache(missing) == {}


def test_append_cache_entry_writes_jsonl(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.jsonl"
    tags = {"module_tags": [_valid_module()], "thema_tags": [], "typ_tags": []}
    _append_cache_entry(cache_path, "chunk_001", tags)

    lines = cache_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["chunk_id"] == "chunk_001"
    assert entry["module_tags"] == [_valid_module()]


def test_load_cache_reads_appended_entries(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.jsonl"
    tags_a = {"module_tags": [_valid_module()], "thema_tags": [], "typ_tags": []}
    tags_b = {
        "module_tags": [],
        "thema_tags": [_valid_thema()],
        "typ_tags": [_valid_typ()],
    }
    _append_cache_entry(cache_path, "chunk_a", tags_a)
    _append_cache_entry(cache_path, "chunk_b", tags_b)

    loaded = _load_cache(cache_path)
    assert "chunk_a" in loaded
    assert "chunk_b" in loaded
    assert loaded["chunk_a"]["module_tags"] == [_valid_module()]
    assert loaded["chunk_b"]["typ_tags"] == [_valid_typ()]


# ── Hauptfunktion mit Mock (3 Tests) ─────────────────────────────────────────


def test_tag_chunks_uses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Chunk im Cache → kein LLM-Call."""
    cache_path = tmp_path / "cache.jsonl"
    chunk_id = "forum__post_001"
    tags = {
        "module_tags": [_valid_module()],
        "thema_tags": [_valid_thema()],
        "typ_tags": [_valid_typ()],
    }
    _append_cache_entry(cache_path, chunk_id, tags)

    call_count: dict[str, int] = {"n": 0}

    def _mock_call_llm(
        messages: list, schema: dict
    ) -> tuple[dict, int, int]:
        call_count["n"] += 1
        return {"module_tags": [], "thema_tags": [], "typ_tags": []}, 0, 0

    monkeypatch.setattr("rag.index.llm_tagger._call_llm", _mock_call_llm)

    chunks = [_make_chunk(chunk_id)]
    tag_chunks(chunks, cache_path=cache_path)

    assert call_count["n"] == 0
    assert chunks[0]["metadata"]["module_tags"] == _valid_module()


def test_tag_chunks_skips_already_tagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mix aus gecachten und neuen Chunks → Mock nur für neue aufgerufen."""
    cache_path = tmp_path / "cache.jsonl"
    cached_id = "forum__cached"
    new_ids = ["forum__new_1", "forum__new_2"]

    _append_cache_entry(
        cache_path,
        cached_id,
        {
            "module_tags": [_valid_module()],
            "thema_tags": [],
            "typ_tags": [],
        },
    )

    call_count: dict[str, int] = {"n": 0}

    def _mock_call_llm(
        messages: list, schema: dict
    ) -> tuple[dict, int, int]:
        call_count["n"] += 1
        return {
            "module_tags": [_valid_module()],
            "thema_tags": [_valid_thema()],
            "typ_tags": [_valid_typ()],
        }, 50, 20

    monkeypatch.setattr("rag.index.llm_tagger._call_llm", _mock_call_llm)

    chunks = [_make_chunk(cached_id)] + [_make_chunk(i) for i in new_ids]
    tag_chunks(chunks, cache_path=cache_path)

    assert call_count["n"] == len(new_ids)


def test_tag_chunks_aborts_on_high_untagged_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM liefert nur leere Tags → Ungetaggt-Rate 100% → RuntimeError."""
    cache_path = tmp_path / "cache.jsonl"

    def _mock_call_llm(
        messages: list, schema: dict
    ) -> tuple[dict, int, int]:
        return {"module_tags": [], "thema_tags": [], "typ_tags": []}, 50, 10

    monkeypatch.setattr("rag.index.llm_tagger._call_llm", _mock_call_llm)

    chunks = [_make_chunk("forum__a"), _make_chunk("forum__b")]
    with pytest.raises(RuntimeError, match="Ungetaggt-Rate"):
        tag_chunks(chunks, cache_path=cache_path)


# ── Integration (1 Test) ─────────────────────────────────────────────────────


def test_tag_chunks_serializes_to_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mock liefert Tags → Chunks haben kommagetrennte Strings in Metadaten."""
    cache_path = tmp_path / "cache.jsonl"
    mod1, mod2 = sorted(MODULE_TAGS)[:2]
    th1, th2 = sorted(THEMA_TAGS)[:2]
    typ1 = sorted(TYP_TAGS)[0]

    def _mock_call_llm(
        messages: list, schema: dict
    ) -> tuple[dict, int, int]:
        return {
            "module_tags": [mod1, mod2],
            "thema_tags": [th1, th2],
            "typ_tags": [typ1],
        }, 100, 20

    monkeypatch.setattr("rag.index.llm_tagger._call_llm", _mock_call_llm)

    chunks = [_make_chunk("forum__serial_001")]
    tag_chunks(chunks, cache_path=cache_path)

    meta = chunks[0]["metadata"]
    assert meta["module_tags"] == f"{mod1},{mod2}"
    assert meta["thema_tags"] == f"{th1},{th2}"
    assert meta["typ_tags"] == typ1
