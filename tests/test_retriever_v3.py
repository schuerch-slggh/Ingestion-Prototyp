"""Integration-Tests für den V3-Retriever (AP-8). Alle I/O-Aufrufe gemockt."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.retrieve.retriever import retrieve_chunks

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _hybrid_chunk(chunk_id: str, rrf_score: float = 0.05) -> dict:
    return {
        "id": chunk_id,
        "text": f"Text {chunk_id}",
        "metadata": {"source_type": "handbuch"},
        "similarity": 0.9,
        "rrf_score": rrf_score,
        "rrf_rank": 1,
    }


# ── Tests ────────────────────────────────────────────────────────────────────


def test_retrieve_v3_dispatches_to_recency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """retrieve_chunks(variant='v3') ruft _retrieve_hybrid_with_recency auf."""
    called: dict[str, bool] = {"recency": False}

    def mock_recency(query: str, top_k: int) -> list[dict]:
        called["recency"] = True
        return [_hybrid_chunk("c1")]

    monkeypatch.setattr(
        "rag.retrieve.retriever._retrieve_hybrid_with_recency",
        mock_recency,
    )

    result = retrieve_chunks("test query", "v3", top_k=5)

    assert called["recency"] is True
    assert len(result) == 1


def test_retrieve_v3_uses_v2_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 ruft intern _retrieve_hybrid mit variant='v2' auf."""
    hybrid_calls: list[dict] = []

    def mock_hybrid(query: str, variant: str, top_k: int) -> list[dict]:
        hybrid_calls.append({"variant": variant, "top_k": top_k})
        return [_hybrid_chunk(f"c{i}", rrf_score=0.05) for i in range(top_k)]

    monkeypatch.setattr(
        "rag.retrieve.retriever._retrieve_hybrid",
        mock_hybrid,
    )

    result = retrieve_chunks("test query", "v3", top_k=3)

    assert len(hybrid_calls) == 1
    assert hybrid_calls[0]["variant"] == "v2"
    # Pre-rerank pool ist >= top_k
    assert hybrid_calls[0]["top_k"] >= 3
    # Finales Ergebnis auf top_k begrenzt
    assert len(result) <= 3
