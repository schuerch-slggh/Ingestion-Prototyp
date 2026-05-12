"""Tests für den RAGAS-Reporter (AP-4.3)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.evaluate.reporter import (
    CategoryAggregate,
    VariantSummary,
    _mean_excluding_none,
    build_summary,
    write_markdown,
)

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _write_scores_json(path: Path, scores: list[dict], n_total: int = None) -> None:
    payload = {
        "metadata": {
            "bundle_path": "runs/eval/v0/responses_test.jsonl",
            "judge_model": "gpt-4o",
            "scored_at": "2026-05-08T10:00:00+00:00",
            "n_total": n_total or len(scores),
            "n_skipped_errors": 0,
            "n_with_ground_truth": len(scores),
        },
        "scores": scores,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _make_score(
    q_id: str,
    category: str,
    faith: float | None = 0.8,
    arel: float | None = 0.7,
    crecall: float | None = 0.6,
    cfact: float | None = 0.5,
) -> dict:
    return {
        "question_id": q_id,
        "category": category,
        "faithfulness": faith,
        "answer_relevance": arel,
        "context_recall": crecall,
        "factual_correctness": cfact,
    }


# ---------------------------------------------------------------------------
# _mean_excluding_none (3 Tests)
# ---------------------------------------------------------------------------


def test_mean_excluding_none_basic() -> None:
    assert _mean_excluding_none([0.5, 0.7, 0.9]) == pytest.approx(0.7)


def test_mean_excluding_none_with_nones() -> None:
    assert _mean_excluding_none([0.5, None, 0.9]) == pytest.approx(0.7)


def test_mean_excluding_none_all_none() -> None:
    assert _mean_excluding_none([None, None]) is None


# ---------------------------------------------------------------------------
# build_summary (1 Test)
# ---------------------------------------------------------------------------


def test_build_summary_aggregates_correctly(tmp_path: Path) -> None:
    """Mittelwerte über alle Einträge und pro Kategorie korrekt berechnet."""
    scores = [
        _make_score("Q001", "Chunking", faith=0.8, arel=0.6, crecall=0.5, cfact=0.4),
        _make_score("Q002", "Chunking", faith=0.6, arel=0.8, crecall=0.7, cfact=0.6),
        _make_score("Q026", "Recency", faith=0.9, arel=0.7, crecall=0.8, cfact=0.7),
        _make_score("Q036", "Visuals", faith=0.7, arel=0.5, crecall=0.4, cfact=0.3),
        _make_score("Q046", "CrossSource", faith=1.0, arel=0.9, crecall=0.9, cfact=0.8),
    ]
    scores_path = tmp_path / "ragas_test.json"
    _write_scores_json(scores_path, scores, n_total=5)

    summary = build_summary(scores_path, "v0")

    assert summary.variant == "v0"
    assert summary.n_total == 5
    assert summary.n_scored == 5
    assert summary.overall.n == 5
    # Faithfulness-Mittelwert: (0.8+0.6+0.9+0.7+1.0)/5 = 0.8
    assert summary.overall.faithfulness_mean == pytest.approx(0.8)

    cats = {agg.category: agg for agg in summary.by_category}
    assert "Chunking" in cats
    assert cats["Chunking"].n == 2
    # Chunking faith: (0.8+0.6)/2 = 0.7
    assert cats["Chunking"].faithfulness_mean == pytest.approx(0.7)
    assert "Recency" in cats
    assert "Visuals" in cats
    assert "CrossSource" in cats


# ---------------------------------------------------------------------------
# write_markdown (1 Test)
# ---------------------------------------------------------------------------


def test_write_markdown_produces_valid_md(tmp_path: Path) -> None:
    """Markdown-Datei enthält alle erwarteten Abschnitte."""
    overall = CategoryAggregate(
        category="ALL",
        n=5,
        faithfulness_mean=0.8,
        answer_relevance_mean=0.7,
        context_recall_mean=0.6,
        factual_correctness_mean=0.5,
    )
    by_cat = [
        CategoryAggregate("Chunking", 2, 0.75, 0.65, 0.55, 0.45),
        CategoryAggregate("Recency", 1, 0.9, 0.8, 0.7, 0.6),
    ]
    summary = VariantSummary(
        variant="v0",
        n_total=5,
        n_scored=5,
        n_with_ground_truth=3,
        overall=overall,
        by_category=by_cat,
        bundle_path=Path("runs/eval/v0/responses_test.jsonl"),
        scores_path=tmp_path / "ragas_test.json",
    )
    out = tmp_path / "summary_test.md"
    write_markdown(summary, out)

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "## Gesamtergebnis" in content
    assert "## Pro Kategorie" in content
    assert "Chunking" in content
    assert "Recency" in content
    assert "0.800" in content  # faithfulness_mean formatted
