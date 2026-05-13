"""Tests für das Recency-Re-Ranking-Modul (AP-8)."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.retrieve.recency_reranker import (
    _compute_recency_score,
    _parse_date,
    apply_recency_reranking,
)

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _forum_chunk(chunk_id: str, post_date: str, rrf_score: float = 0.05) -> dict:
    return {
        "id": chunk_id,
        "text": f"Text {chunk_id}",
        "rrf_score": rrf_score,
        "metadata": {"source_type": "forum", "post_date": post_date},
    }


def _handbuch_chunk(chunk_id: str, rrf_score: float = 0.05) -> dict:
    return {
        "id": chunk_id,
        "text": f"Text {chunk_id}",
        "rrf_score": rrf_score,
        "metadata": {"source_type": "handbuch"},
    }


# ── Datumsverarbeitung (3 Tests) ─────────────────────────────────────────────


def test_parse_date_valid_iso() -> None:
    """Valides ISO-Datum wird korrekt geparst."""
    assert _parse_date("2024-03-15") == date(2024, 3, 15)


def test_parse_date_invalid_returns_none() -> None:
    """Ungültiges Format liefert None."""
    assert _parse_date("not-a-date") is None


def test_parse_date_empty_returns_none() -> None:
    """Leerer String liefert None."""
    assert _parse_date("") is None


# ── Recency-Score-Berechnung (3 Tests) ───────────────────────────────────────


def test_compute_recency_undated_source_returns_1() -> None:
    """Nicht-datierte Quelle (Handbuch) ergibt Recency-Score 1.0."""
    chunk = {"metadata": {"source_type": "handbuch", "doc_title": "Test"}}
    score = _compute_recency_score(chunk, date(2026, 5, 12))
    assert score == 1.0


def test_compute_recency_today_forum_returns_1() -> None:
    """Forum-Chunk mit heutigem Datum ergibt Score nahe 1.0."""
    chunk = {
        "metadata": {
            "source_type": "forum",
            "post_date": "2026-05-12",
        }
    }
    score = _compute_recency_score(chunk, date(2026, 5, 12))
    assert score == pytest.approx(1.0, abs=1e-6)


def test_compute_recency_old_forum_decays() -> None:
    """Forum-Chunk mit Datum 5 Jahre zurück ergibt Score ~0.5 (Halbwertszeit)."""
    chunk = {
        "metadata": {
            "source_type": "forum",
            "post_date": "2021-05-12",
        }
    }
    score = _compute_recency_score(chunk, date(2026, 5, 12))
    # 5 Jahre = ~1826 Tage ≈ Halbwertszeit (1825 Tage) → exp(-ln2) ≈ 0.500
    assert score == pytest.approx(0.500, abs=0.01)


# ── Re-Ranking-Logik (2 Tests) ───────────────────────────────────────────────


def test_apply_reranking_reorders_by_final_score() -> None:
    """Altes Forum wird durch Recency-Abwertung ans Ende sortiert."""
    chunks = [
        _forum_chunk("old_forum", "2018-05-12", rrf_score=0.05),
        _handbuch_chunk("handbuch", rrf_score=0.05),
        _forum_chunk("new_forum", "2026-05-12", rrf_score=0.05),
    ]
    today = date(2026, 5, 12)
    result = apply_recency_reranking(chunks, today=today, top_k=3)

    assert len(result) == 3
    assert result[-1]["id"] == "old_forum"
    # new_forum und handbuch haben recency=1.0 → stehen vor old_forum
    top_two_ids = {result[0]["id"], result[1]["id"]}
    assert top_two_ids == {"new_forum", "handbuch"}


def test_apply_reranking_respects_top_k() -> None:
    """10 Chunks als Input, top_k=5 → genau 5 zurück."""
    chunks = [
        _handbuch_chunk(f"c{i}", rrf_score=0.1) for i in range(10)
    ]
    today = date(2026, 5, 12)
    result = apply_recency_reranking(chunks, today=today, top_k=5)
    assert len(result) == 5
