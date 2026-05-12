"""Tests für das Test-Set-Modul (AP-4.1/6.4)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.evaluate.testset import (
    TestQuestion,
    iter_by_category,
    load_testset,
    validate_entry,
)

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries),
        encoding="utf-8",
    )


def _valid_entry(n: int = 1, category: str = "Chunking") -> dict:
    return {"id": f"Q{n:03d}", "question": f"Testfrage {n}?", "category": category}


# ---------------------------------------------------------------------------
# Schema-Validierung (5 Tests)
# ---------------------------------------------------------------------------


def test_validate_entry_minimal_valid() -> None:
    """Gültiger Eintrag wird korrekt zu TestQuestion konvertiert."""
    entry = {"id": "Q001", "question": "Wie geht das?", "category": "Chunking"}
    q = validate_entry(entry)
    assert isinstance(q, TestQuestion)
    assert q.id == "Q001"
    assert q.question == "Wie geht das?"
    assert q.category == "Chunking"


def test_validate_entry_missing_field() -> None:
    """Fehlendes Pflichtfeld 'question' wirft ValueError."""
    entry = {"id": "Q001", "category": "Chunking"}
    with pytest.raises(ValueError, match="question"):
        validate_entry(entry)


def test_validate_entry_invalid_id_format() -> None:
    """ID 'Q1' (kein dreistelliges Format) wirft ValueError."""
    entry = {"id": "Q1", "question": "Testfrage?", "category": "Chunking"}
    with pytest.raises(ValueError, match="ID"):
        validate_entry(entry)


def test_validate_entry_invalid_category() -> None:
    """Kategorie 'chunking' (Kleinschreibung) wirft ValueError."""
    entry = {"id": "Q001", "question": "Testfrage?", "category": "chunking"}
    with pytest.raises(ValueError, match="Kategorie"):
        validate_entry(entry)


def test_validate_entry_empty_question() -> None:
    """Frage '   ' (nur Whitespace) wirft ValueError."""
    entry = {"id": "Q001", "question": "   ", "category": "Chunking"}
    with pytest.raises(ValueError, match="question"):
        validate_entry(entry)


# ---------------------------------------------------------------------------
# Loader (4 Tests)
# ---------------------------------------------------------------------------


def test_load_testset_valid_file(tmp_path: Path) -> None:
    """Valide JSONL mit 3 Einträgen wird vollständig geladen."""
    f = tmp_path / "ts.jsonl"
    _write_jsonl(f, [_valid_entry(i) for i in range(1, 4)])
    questions = load_testset(f)
    assert len(questions) == 3
    assert questions[0].id == "Q001"
    assert questions[2].id == "Q003"


def test_load_testset_missing_file(tmp_path: Path) -> None:
    """Nicht existente Datei wirft FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_testset(tmp_path / "nope.jsonl")


def test_load_testset_skips_blank_lines(tmp_path: Path) -> None:
    """Leerzeilen in der JSONL werden ignoriert."""
    f = tmp_path / "ts.jsonl"
    content = (
        json.dumps(_valid_entry(1)) + "\n"
        "\n"
        + json.dumps(_valid_entry(2)) + "\n"
        "\n"
    )
    f.write_text(content, encoding="utf-8")
    questions = load_testset(f)
    assert len(questions) == 2


def test_load_testset_invalid_json_line(tmp_path: Path) -> None:
    """Syntax-Fehler in einer Zeile wirft ValueError mit Zeilennummer."""
    f = tmp_path / "ts.jsonl"
    f.write_text(
        json.dumps(_valid_entry(1)) + "\n"
        "{not valid json}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Zeile 2"):
        load_testset(f)


# ---------------------------------------------------------------------------
# Konsistenzchecks (2 Tests)
# ---------------------------------------------------------------------------


def test_consistency_duplicate_ids_logs_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Duplikat-IDs erzeugen eine Warnung im Log."""
    f = tmp_path / "ts.jsonl"
    _write_jsonl(f, [_valid_entry(1), _valid_entry(1)])  # Q001 zweimal
    import logging
    with caplog.at_level(logging.WARNING, logger="rag.evaluate.testset"):
        load_testset(f)
    assert any("Duplikat" in r.message for r in caplog.records)


def test_consistency_id_gaps_log_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Lücke in ID-Sequenz (Q001, Q003 ohne Q002) erzeugt Warnung."""
    f = tmp_path / "ts.jsonl"
    _write_jsonl(f, [_valid_entry(1), _valid_entry(3)])
    import logging
    with caplog.at_level(logging.WARNING, logger="rag.evaluate.testset"):
        load_testset(f)
    assert any("Q002" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Filter / Iter (2 Tests)
# ---------------------------------------------------------------------------


def test_iter_by_category_groups_correctly() -> None:
    """Korrekte Listen in der richtigen Kategorie-Reihenfolge."""
    questions = [
        TestQuestion(id="Q001", question="a?", category="Recency"),
        TestQuestion(id="Q002", question="b?", category="Chunking"),
        TestQuestion(id="Q003", question="c?", category="Recency"),
    ]
    result = list(iter_by_category(questions))
    assert result[0][0] == "Chunking"
    assert len(result[0][1]) == 1
    assert result[1][0] == "Recency"
    assert len(result[1][1]) == 2


# ---------------------------------------------------------------------------
# Ground-Truth-Feld (2 Tests)
# ---------------------------------------------------------------------------


def test_load_testset_with_ground_truth(tmp_path: Path) -> None:
    """Eintrag mit gefülltem ground_truth wird korrekt geladen."""
    f = tmp_path / "ts.jsonl"
    f.write_text(
        '{"id": "Q001", "question": "Test?", "category": "Chunking", '
        '"ground_truth": "Test answer."}\n',
        encoding="utf-8",
    )
    questions = load_testset(f)
    assert len(questions) == 1
    assert questions[0].ground_truth == "Test answer."


def test_load_testset_without_ground_truth(tmp_path: Path) -> None:
    """Eintrag ohne ground_truth-Feld wird mit Default-Wert geladen."""
    f = tmp_path / "ts.jsonl"
    f.write_text(
        '{"id": "Q001", "question": "Test?", "category": "Chunking"}\n',
        encoding="utf-8",
    )
    questions = load_testset(f)
    assert questions[0].ground_truth == ""


def test_iter_by_category_skips_empty_categories() -> None:
    """Kategorien ohne Einträge erscheinen nicht im Output."""
    questions = [
        TestQuestion(id="Q001", question="a?", category="Visuals"),
    ]
    categories = [cat for cat, _ in iter_by_category(questions)]
    assert categories == ["Visuals"]
    assert "Chunking" not in categories
    assert "Recency" not in categories
    assert "CrossSource" not in categories
