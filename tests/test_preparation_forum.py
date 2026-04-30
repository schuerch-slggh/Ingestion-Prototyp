"""Tests für die Forum-Datenaufbereitung (Bronze → Silver → Gold)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.preparation.forum import clean_to_silver, load_bronze, transform_to_gold
from rag.preparation.lookups import FORUM_MODULE_LOOKUP


def _make_row(
    post_id: str = "1",
    topic_id: str = "10",
    forum_id: str = "15",
    post_time: str = "1600000000",
    post_subject: str = "Betreff",
    post_text: str = "Text",
) -> list[str]:
    """Erzeugt eine Zeile mit 26 phpBB-Spalten; relevante Felder setzbar."""
    row = [""] * 26
    row[0] = post_id
    row[1] = topic_id
    row[2] = forum_id
    row[6] = post_time
    row[14] = post_subject
    row[15] = post_text
    return row


def _to_csv(rows: list[list[str]], sep: str = ";") -> str:
    return "\n".join(sep.join(r) for r in rows)


# ── Schritt 1: load_bronze ───────────────────────────────────────────────────


def test_load_bronze_filters_columns(tmp_path: Path) -> None:
    """load_bronze() liefert genau die sechs Zielspalten mit korrekten Namen."""
    rows = [
        _make_row(post_id="1", topic_id="10", forum_id="15",
                  post_subject="Frage", post_text="Antwort"),
        _make_row(post_id="2", topic_id="11", forum_id="20",
                  post_subject="Problem", post_text="Lösung"),
    ]
    source = tmp_path / "Forum_Export.csv"
    source.write_text(_to_csv(rows), encoding="utf-8")

    df = load_bronze(source)

    assert list(df.columns) == [
        "post_id", "topic_id", "forum_id", "post_time", "post_subject", "post_text"
    ]
    assert len(df) == 2
    assert df.iloc[0]["post_id"] == "1"
    assert df.iloc[0]["post_subject"] == "Frage"
    assert df.iloc[1]["post_text"] == "Lösung"


def test_load_bronze_sample_size(tmp_path: Path) -> None:
    """load_bronze(sample_size=N) gibt maximal N Zeilen zurück."""
    rows = [_make_row(post_id=str(i), post_text=f"Text {i}") for i in range(1, 11)]
    source = tmp_path / "Forum_Export.csv"
    source.write_text(_to_csv(rows), encoding="utf-8")

    df = load_bronze(source, sample_size=5)

    assert len(df) == 5


# ── Schritt 2: clean_to_silver ───────────────────────────────────────────────


def _silver_input(**kwargs: object) -> pd.DataFrame:
    """Erzeugt einen Minimal-DataFrame für clean_to_silver()."""
    defaults = {
        "post_id": "1",
        "topic_id": "10",
        "forum_id": "15",
        "post_time": 1600000000,
        "post_subject": "Betreff",
        "post_text": "Text",
    }
    defaults.update(kwargs)
    return pd.DataFrame([defaults])


def test_clean_to_silver_removes_html_and_bbcode() -> None:
    """clean_to_silver() entfernt HTML- und BBCode-Tags aus subject und text."""
    df = _silver_input(
        post_subject="[b]Wichtige Frage[/b]",
        post_text=(
            "<p>Hallo <b>Welt</b></p> "
            "[url=http://example.com]Link[/url] "
            "[quote]Zitat[/quote]"
        ),
    )

    result = clean_to_silver(df)
    subject = result.iloc[0]["post_subject"]
    text = result.iloc[0]["post_text"]

    assert "<" not in subject and ">" not in subject
    assert "[" not in subject and "]" not in subject
    assert "Wichtige Frage" in subject

    assert "<" not in text and ">" not in text
    assert "[" not in text and "]" not in text
    assert "Hallo" in text and "Welt" in text
    assert "Link" in text
    assert "Zitat" in text


def test_clean_to_silver_resolves_module_codes() -> None:
    """Bekannte forum_id wird aufgelöst; unbekannte bleibt als String erhalten."""
    df = pd.DataFrame([
        {"post_id": "1", "topic_id": "10", "forum_id": "15",
         "post_time": 1600000000, "post_subject": "A", "post_text": "Text A"},
        {"post_id": "2", "topic_id": "11", "forum_id": "999",
         "post_time": 1600000001, "post_subject": "B", "post_text": "Text B"},
    ])

    result = clean_to_silver(df)

    assert result[result["post_id"] == "1"].iloc[0]["module"] == "SelectLine Auftrag"
    assert result[result["post_id"] == "2"].iloc[0]["module"] == "999"


def test_clean_to_silver_drops_empty_and_deduplicates() -> None:
    """Leere post_text-Felder und Duplikate werden entfernt."""
    df = pd.DataFrame([
        {"post_id": "1", "topic_id": "1", "forum_id": "15",
         "post_time": 1600000000, "post_subject": "A", "post_text": "Gleicher Text"},
        {"post_id": "2", "topic_id": "1", "forum_id": "15",
         "post_time": 1600000001, "post_subject": "B", "post_text": "Gleicher Text"},
        {"post_id": "3", "topic_id": "2", "forum_id": "15",
         "post_time": 1600000002, "post_subject": "C", "post_text": "   "},
    ])

    result = clean_to_silver(df)

    assert len(result) == 1
    assert result.iloc[0]["post_id"] == "1"


# ── Schritt 3: transform_to_gold ─────────────────────────────────────────────


def test_transform_to_gold_produces_correct_schema() -> None:
    """Gold-Records haben das korrekte Schema und kombinieren Titel + Text."""
    df = pd.DataFrame([
        {"post_id": "1", "topic_id": "10", "module": "SelectLine Auftrag",
         "post_date": "2020-09-13", "post_subject": "Wie richte ich X ein?",
         "post_text": "Ich habe folgendes Problem..."},
        {"post_id": "2", "topic_id": "10", "module": "SelectLine Lohn",
         "post_date": "2020-09-14", "post_subject": "Antwort zu X",
         "post_text": "Du musst Y konfigurieren."},
        {"post_id": "3", "topic_id": "11", "module": "Programmübergreifend",
         "post_date": "2020-10-01", "post_subject": "Bug in Version 18",
         "post_text": "Nach dem Update tritt folgender Fehler auf..."},
    ])

    records = transform_to_gold(df)

    assert len(records) == 3

    r = records[0]
    assert r["doc_id"] == "forum_1"
    assert r["source_type"] == "forum"
    assert set(r["metadata"].keys()) == {
        "post_id", "topic_id", "module", "post_date", "title"
    }
    assert r["metadata"]["title"] == "Wie richte ich X ein?"
    assert r["metadata"]["module"] == "SelectLine Auftrag"
    assert "full_text" in r["content"]
    assert r["content"]["full_text"] == (
        "Wie richte ich X ein?\n\nIch habe folgendes Problem..."
    )

    # Alle drei Records haben das korrekte Schema
    for rec in records:
        assert {"doc_id", "source_type", "metadata", "content"} == set(rec.keys())
        assert "full_text" in rec["content"]
        assert rec["source_type"] == "forum"
        assert rec["doc_id"].startswith("forum_")
