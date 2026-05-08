"""Tests für den RAGAS-Scorer (AP-4.3)."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.evaluate.scorer import (
    RagasScores,
    _build_ragas_dataset,
    _extract_scores,
    _persist_scores,
    score_bundle,
)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _make_bundle_entry(
    q_id: str = "Q001",
    category: str = "Chunking",
    error: str | None = None,
) -> dict:
    if error is not None:
        return {"question_id": q_id, "category": category, "result": None, "error": error}
    return {
        "question_id": q_id,
        "category": category,
        "error": None,
        "result": {
            "query": f"Frage {q_id}?",
            "answer": f"Antwort zu {q_id}.",
            "retrieved_contexts": ["Kontext A", "Kontext B"],
            "retrieved_chunks": [
                {"text": "Kontext A", "id": "c1", "metadata": {}, "similarity": 0.9},
                {"text": "Kontext B", "id": "c2", "metadata": {}, "similarity": 0.8},
            ],
            "metadata": {"input_tokens": 100, "output_tokens": 50, "duration_seconds": 1.0},
        },
    }


def _write_bundle(path: Path, entries: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries),
        encoding="utf-8",
    )


def _make_mock_ragas_result(
    n: int,
    faith: float = 0.8,
    arel: float = 0.7,
    cprec: float = 0.6,
) -> MagicMock:
    """Synthetisches RAGAS-EvaluationResult-Mock mit n Zeilen."""
    import pandas as pd

    df = pd.DataFrame(
        {
            "faithfulness": [faith] * n,
            "answer_relevancy": [arel] * n,
            "llm_context_precision_without_reference": [cprec] * n,
        }
    )
    mock = MagicMock()
    mock.to_pandas.return_value = df
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_score_bundle_creates_output(tmp_path: Path) -> None:
    """Output-Datei wird erzeugt mit korrekter Anzahl Scores."""
    bundle = tmp_path / "bundle.jsonl"
    out = tmp_path / "scores.json"
    entries = [_make_bundle_entry(f"Q{i:03d}") for i in range(1, 4)]
    _write_bundle(bundle, entries)

    mock_result = _make_mock_ragas_result(3)
    with (
        patch("rag.evaluate.scorer._configure_judge", return_value=MagicMock()),
        patch("rag.evaluate.scorer.evaluate", return_value=mock_result),
    ):
        score_bundle(bundle, out)

    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["scores"]) == 3


def test_score_bundle_filters_error_entries(tmp_path: Path) -> None:
    """Einträge mit error != null werden aus dem RAGAS-Dataset herausgefiltert."""
    bundle = tmp_path / "bundle.jsonl"
    out = tmp_path / "scores.json"
    entries = [
        _make_bundle_entry("Q001"),
        _make_bundle_entry("Q002", error="Fehler"),
        _make_bundle_entry("Q003"),
    ]
    _write_bundle(bundle, entries)

    mock_result = _make_mock_ragas_result(2)
    captured: list = []

    def fake_evaluate(dataset, **kwargs):
        captured.append(dataset)
        return mock_result

    with (
        patch("rag.evaluate.scorer._configure_judge", return_value=MagicMock()),
        patch("rag.evaluate.scorer.evaluate", side_effect=fake_evaluate),
    ):
        score_bundle(bundle, out)

    # Nur 2 Samples dürfen im Dataset gewesen sein
    assert len(captured[0].samples) == 2


def test_score_bundle_raises_when_all_errors(tmp_path: Path) -> None:
    """Nur Fehler-Einträge → ValueError."""
    bundle = tmp_path / "bundle.jsonl"
    out = tmp_path / "scores.json"
    entries = [_make_bundle_entry(f"Q{i:03d}", error="fail") for i in range(1, 4)]
    _write_bundle(bundle, entries)

    with pytest.raises(ValueError, match="keine erfolgreichen"):
        score_bundle(bundle, out)


def test_build_ragas_dataset_schema() -> None:
    """Mapping von Bundle-Einträgen auf SingleTurnSample-Felder ist korrekt."""
    entries = [_make_bundle_entry("Q001"), _make_bundle_entry("Q002")]
    dataset = _build_ragas_dataset(entries)
    assert len(dataset.samples) == 2
    s = dataset.samples[0]
    assert s.user_input == "Frage Q001?"
    assert s.response == "Antwort zu Q001."
    assert s.retrieved_contexts == ["Kontext A", "Kontext B"]


def test_extract_scores_preserves_order() -> None:
    """Scores werden in Bundle-Reihenfolge zurückgegeben."""
    entries = [
        _make_bundle_entry("Q010", "Recency"),
        _make_bundle_entry("Q020", "Visuals"),
    ]
    mock_result = _make_mock_ragas_result(2, faith=0.9, arel=0.8, cprec=0.7)
    scores = _extract_scores(mock_result, entries)
    assert len(scores) == 2
    assert scores[0].question_id == "Q010"
    assert scores[0].category == "Recency"
    assert scores[0].faithfulness == pytest.approx(0.9)
    assert scores[1].question_id == "Q020"
    assert scores[1].answer_relevance == pytest.approx(0.8)


def test_persist_scores_writes_metadata(tmp_path: Path) -> None:
    """JSON enthält metadata mit bundle_path, judge_model, scored_at."""
    scores = [
        RagasScores(
            question_id="Q001",
            category="Chunking",
            faithfulness=0.8,
            answer_relevance=0.7,
            context_precision=0.6,
        )
    ]
    bundle = tmp_path / "responses_test.jsonl"
    out = tmp_path / "ragas_test.json"
    _persist_scores(scores, out, bundle, "gpt-4o", n_skipped_errors=1)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["metadata"]["judge_model"] == "gpt-4o"
    assert "bundle_path" in payload["metadata"]
    assert "scored_at" in payload["metadata"]
    assert payload["metadata"]["n_total"] == 2  # 1 score + 1 skipped
    assert payload["metadata"]["n_skipped_errors"] == 1
