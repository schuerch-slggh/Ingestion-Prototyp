"""Tests für den Evaluation-Runner (AP-4.2)."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.evaluate.runner import (
    BundleEntry,
    _aggregate_stats,
    _select_dry_run_subset,
    run_testset,
)
from rag.evaluate.testset import TestQuestion, load_testset


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _make_questions(n: int = 3, category: str = "Chunking") -> list[TestQuestion]:
    return [
        TestQuestion(id=f"Q{i:03d}", question=f"Frage {i}?", category=category)
        for i in range(1, n + 1)
    ]


def _make_result(q_id: str = "Q001") -> dict:
    return {
        "query": f"Frage {q_id}?",
        "answer": "Antwort.",
        "retrieved_chunks": [],
        "metadata": {
            "input_tokens": 100,
            "output_tokens": 50,
            "duration_seconds": 1.5,
        },
    }


# ---------------------------------------------------------------------------
# run_testset (5 Tests)
# ---------------------------------------------------------------------------


def test_run_testset_creates_output_file(tmp_path: Path) -> None:
    """Output-Datei wird erzeugt und enthält die korrekte Anzahl Zeilen."""
    questions = _make_questions(3)
    out = tmp_path / "bundle.jsonl"

    with patch(
        "rag.evaluate.runner.answer_query",
        side_effect=lambda q, v: _make_result(),
    ):
        run_testset(questions, "v0", out)

    assert out.exists()
    lines = [l for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3


def test_run_testset_writes_jsonl_schema(tmp_path: Path) -> None:
    """Jede Zeile enthält die Felder question_id, category, result, error."""
    questions = _make_questions(2)
    out = tmp_path / "bundle.jsonl"

    with patch(
        "rag.evaluate.runner.answer_query",
        side_effect=lambda q, v: _make_result(),
    ):
        run_testset(questions, "v0", out)

    for raw in out.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        entry = json.loads(raw)
        assert "question_id" in entry
        assert "category" in entry
        assert "result" in entry
        assert "error" in entry


def test_run_testset_handles_exception(tmp_path: Path) -> None:
    """Exception bei einer Frage → error-Eintrag, Lauf geht weiter."""
    questions = _make_questions(3)
    out = tmp_path / "bundle.jsonl"

    call_count = 0

    def patched(q: str, v: str) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("API-Fehler simuliert")
        return _make_result()

    with patch("rag.evaluate.runner.answer_query", side_effect=patched):
        run_testset(questions, "v0", out)

    lines = [
        json.loads(l)
        for l in out.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert len(lines) == 3
    error_entries = [e for e in lines if e["error"] is not None]
    success_entries = [e for e in lines if e["result"] is not None]
    assert len(error_entries) == 1
    assert len(success_entries) == 2
    assert lines[1]["result"] is None
    assert "API-Fehler simuliert" in lines[1]["error"]


def test_run_testset_aborts_on_high_error_rate(tmp_path: Path) -> None:
    """Mehr als 50% Fehler nach ≥5 Fragen → RuntimeError."""
    questions = _make_questions(10)
    out = tmp_path / "bundle.jsonl"

    with patch(
        "rag.evaluate.runner.answer_query",
        side_effect=RuntimeError("immer Fehler"),
    ):
        with pytest.raises(RuntimeError, match="Fehlerquote"):
            run_testset(questions, "v0", out)


def test_run_testset_creates_directory(tmp_path: Path) -> None:
    """Output-Verzeichnis wird bei Bedarf angelegt."""
    questions = _make_questions(1)
    nested = tmp_path / "tief" / "verschachtelt" / "bundle.jsonl"
    assert not nested.parent.exists()

    with patch(
        "rag.evaluate.runner.answer_query",
        side_effect=lambda q, v: _make_result(),
    ):
        run_testset(questions, "v0", nested)

    assert nested.parent.exists()
    assert nested.exists()


# ---------------------------------------------------------------------------
# _select_dry_run_subset (2 Tests)
# ---------------------------------------------------------------------------


def test_select_dry_run_subset_returns_5() -> None:
    """Dry-Run-Subset aus dem echten Test-Set enthält genau 5 Fragen."""
    questions = load_testset()
    subset = _select_dry_run_subset(questions)
    assert len(subset) == 5


def test_select_dry_run_subset_covers_all_categories() -> None:
    """Subset deckt alle 4 Kategorien ab (Chunking 2x, andere je 1x)."""
    questions = load_testset()
    subset = _select_dry_run_subset(questions)

    from collections import Counter
    cats = Counter(q.category for q in subset)
    assert cats["Chunking"] == 2
    assert cats["Recency"] == 1
    assert cats["Visuals"] == 1
    assert cats["CrossSource"] == 1


# ---------------------------------------------------------------------------
# _aggregate_stats (1 Test)
# ---------------------------------------------------------------------------


def test_aggregate_stats_excludes_errors() -> None:
    """Fehler-Einträge werden aus Token-Summen ausgeschlossen."""
    entries = [
        BundleEntry(
            question_id=f"Q{i:03d}",
            category="Chunking",
            result={
                "metadata": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "duration_seconds": 1.0,
                }
            },
            error=None,
        )
        for i in range(1, 4)
    ] + [
        BundleEntry(
            question_id="Q004",
            category="Chunking",
            result=None,
            error="Fehler",
        )
    ]

    stats = _aggregate_stats(entries)
    assert stats["n_total"] == 4
    assert stats["n_success"] == 3
    assert stats["n_error"] == 1
    assert stats["total_input_tokens"] == 300
    assert stats["total_output_tokens"] == 150
    assert stats["total_duration_s"] == pytest.approx(3.0)
