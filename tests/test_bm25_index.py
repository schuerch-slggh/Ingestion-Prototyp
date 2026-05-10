"""Tests für den BM25-Index (AP-6.1c)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.index.bm25_index import _tokenize, build_bm25_index, search_bm25


def _make_chunk(chunk_id: str, keywords: str) -> dict:
    return {"id": chunk_id, "text": "Text.", "metadata": {"keywords": keywords}}


# ── Tokenisierung (1 Test) ───────────────────────────────────────────────────


def test_tokenize_basic() -> None:
    tokens = _tokenize("Auftrag MWST Buchung 2024")
    assert "auftrag" in tokens
    assert "mwst" in tokens
    assert "buchung" in tokens
    assert "2024" in tokens
    # Upper-case must be lowercased
    assert "Auftrag" not in tokens


# ── Index-Aufbau (1 Test) ────────────────────────────────────────────────────


def test_build_bm25_index_creates_file(tmp_path: Path) -> None:
    chunks = [
        _make_chunk("c1", "auftrag,mwst"),
        _make_chunk("c2", "lohn,buchung"),
    ]
    output = tmp_path / "bm25.pkl"
    build_bm25_index(chunks, output)
    assert output.exists()
    assert output.stat().st_size > 0


# ── Suche (2 Tests) ──────────────────────────────────────────────────────────


def test_search_bm25_returns_top_k(tmp_path: Path) -> None:
    chunks = [
        _make_chunk("c1", "auftrag,mwst,buchung"),
        _make_chunk("c2", "lohn,personalabrechnung"),
        _make_chunk("c3", "auftrag,lieferschein,rechnung"),
    ]
    index_path = tmp_path / "bm25.pkl"
    build_bm25_index(chunks, index_path)

    results = search_bm25("auftrag rechnung", index_path, top_k=2)

    assert len(results) <= 2
    # Chunks with "auftrag" must rank higher
    chunk_ids = [r["chunk_id"] for r in results]
    assert "c1" in chunk_ids or "c3" in chunk_ids
    # Result structure
    for r in results:
        assert "chunk_id" in r
        assert "rank" in r
        assert "score" in r
        assert r["score"] > 0


def test_search_bm25_filters_zero_scores(tmp_path: Path) -> None:
    chunks = [
        _make_chunk("c1", "auftrag,mwst"),
        _make_chunk("c2", "lohn,buchung"),
    ]
    index_path = tmp_path / "bm25.pkl"
    build_bm25_index(chunks, index_path)

    results = search_bm25("vollkommen_unbekanntes_wort_xyz", index_path)
    assert results == []
