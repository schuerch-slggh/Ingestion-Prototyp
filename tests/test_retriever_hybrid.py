"""Tests für das Hybrid-Retrieval (AP-6.1c). Alle I/O-Aufrufe sind gemockt."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.retrieve.retriever import RRF_K_CONSTANT, retrieve_chunks


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _embed_chunk(chunk_id: str, rank: int) -> dict:
    return {
        "id": chunk_id,
        "text": f"Text {chunk_id}",
        "metadata": {"source_type": "forum"},
        "similarity": round(1.0 - rank * 0.1, 4),
    }


def _bm25_result(chunk_id: str, rank: int) -> dict:
    return {"chunk_id": chunk_id, "rank": rank, "score": 1.0 / rank}


# ── Tests ────────────────────────────────────────────────────────────────────


def test_retrieve_hybrid_combines_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embedding + BM25 → RRF kombiniert korrekt, chunk_A ist Top-1."""
    embed_results = [_embed_chunk("c_a", 1), _embed_chunk("c_b", 2)]
    bm25_results = [_bm25_result("c_a", 1), _bm25_result("c_c", 2)]

    monkeypatch.setattr(
        "rag.retrieve.retriever._retrieve_embedding",
        lambda q, v, top_k: embed_results,
    )
    monkeypatch.setattr(
        "rag.retrieve.retriever.search_bm25",
        lambda q, p, top_k: bm25_results,
    )
    monkeypatch.setattr(
        "rag.retrieve.retriever._load_chunk_by_id",
        lambda cid, v: _embed_chunk(cid, 99),
    )

    results = retrieve_chunks("test query", "v2", top_k=3)

    assert len(results) <= 3
    # c_a ranks highest (in both lists at rank 1)
    assert results[0]["id"] == "c_a"
    # All chunks have rrf_score and rrf_rank
    for r in results:
        assert "rrf_score" in r
        assert "rrf_rank" in r


def test_retrieve_hybrid_handles_only_embedding_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BM25 leer → nur Embedding-Resultate, kein _load_chunk_by_id."""
    embed_results = [_embed_chunk("c_x", 1), _embed_chunk("c_y", 2)]

    load_calls: dict[str, int] = {"n": 0}

    def _mock_load(cid: str, v: str) -> dict:
        load_calls["n"] += 1
        return _embed_chunk(cid, 99)

    monkeypatch.setattr(
        "rag.retrieve.retriever._retrieve_embedding",
        lambda q, v, top_k: embed_results,
    )
    monkeypatch.setattr(
        "rag.retrieve.retriever.search_bm25",
        lambda q, p, top_k: [],
    )
    monkeypatch.setattr("rag.retrieve.retriever._load_chunk_by_id", _mock_load)

    results = retrieve_chunks("test", "v2", top_k=5)

    assert len(results) == 2
    assert load_calls["n"] == 0
    assert {r["id"] for r in results} == {"c_x", "c_y"}


def test_retrieve_hybrid_handles_only_bm25_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embedding leer → BM25-Treffer über _load_chunk_by_id geladen."""
    bm25_results = [_bm25_result("c_p", 1), _bm25_result("c_q", 2)]

    loaded_ids: list[str] = []

    def _mock_load(cid: str, v: str) -> dict:
        loaded_ids.append(cid)
        return _embed_chunk(cid, 99)

    monkeypatch.setattr(
        "rag.retrieve.retriever._retrieve_embedding",
        lambda q, v, top_k: [],
    )
    monkeypatch.setattr(
        "rag.retrieve.retriever.search_bm25",
        lambda q, p, top_k: bm25_results,
    )
    monkeypatch.setattr("rag.retrieve.retriever._load_chunk_by_id", _mock_load)

    results = retrieve_chunks("test", "v2", top_k=5)

    assert len(results) == 2
    assert set(loaded_ids) == {"c_p", "c_q"}


def test_rrf_score_calculation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bekannte Ränge → RRF-Score entspricht Formel 1/(k+r1) + 1/(k+r2)."""
    # Chunk is rank 1 in both lists
    embed_results = [_embed_chunk("c_only", 1)]
    bm25_results = [_bm25_result("c_only", 1)]

    monkeypatch.setattr(
        "rag.retrieve.retriever._retrieve_embedding",
        lambda q, v, top_k: embed_results,
    )
    monkeypatch.setattr(
        "rag.retrieve.retriever.search_bm25",
        lambda q, p, top_k: bm25_results,
    )

    results = retrieve_chunks("test", "v2", top_k=5)

    assert len(results) == 1
    expected_score = 2.0 / (RRF_K_CONSTANT + 1)
    assert abs(results[0]["rrf_score"] - expected_score) < 1e-10
