"""Tests für die Modulbeschreibungen-Datenaufbereitung (AP-2d)."""

import json
import logging
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.preparation.modulbeschreibungen import clean_to_silver, transform_to_gold


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _make_doc(
    doc_id: str = "modul_test",
    outline: list | None = None,
    full_text: str = "Normaler Inhalt der Modulbeschreibung.",
) -> dict:
    """Erstellt ein minimales synthetisches Dokument-Dict."""
    return {
        "doc_id": doc_id,
        "filename": f"{doc_id}.pdf",
        "page_count": 5,
        "full_text": full_text,
        "outline": outline if outline is not None else [],
        "images": [],
        "pages": [{"page_number": 1, "text": full_text}],
    }


def _make_silver_row(doc_id: str = "modul_test", outline: list | None = None) -> dict:
    """Erstellt eine Silver-DataFrame-Zeile."""
    return {
        "doc_id": doc_id,
        "filename": f"{doc_id}.pdf",
        "page_count": 5,
        "full_text": "Inhalt der Modulbeschreibung.",
        "outline_json": json.dumps(outline or []),
        "pages_json": json.dumps([{"page_number": 1, "text": "Seitentext"}]),
        "images_json": json.dumps([]),
        "image_count": 0,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_clean_to_silver_handles_empty_outline() -> None:
    """Dokumente ohne Outline müssen fehlerfrei verarbeitet werden."""
    documents = [_make_doc(outline=[])]
    df = clean_to_silver(documents)

    assert len(df) == 1
    outline = json.loads(df.iloc[0]["outline_json"])
    assert outline == [], "Leere Outline muss als leere Liste gespeichert werden"
    assert df.iloc[0]["full_text"] != "", "full_text darf nicht leer sein"


def test_clean_to_silver_logs_outline_statistics(caplog: pytest.LogCaptureFixture) -> None:
    """clean_to_silver muss die Outline-Statistik (mit/ohne) ins Log schreiben."""
    documents = [
        _make_doc("modul_a", outline=[{"level": 1, "title": "Kap 1", "page": 1}]),
        _make_doc("modul_b", outline=[]),
        _make_doc("modul_c", outline=[]),
    ]
    with caplog.at_level(logging.INFO, logger="rag.preparation.modulbeschreibungen"):
        clean_to_silver(documents)

    log_text = caplog.text
    assert "1" in log_text, "Anzahl Dokumente mit Outline muss geloggt werden"
    assert "2" in log_text, "Anzahl Dokumente ohne Outline muss geloggt werden"
    # Die spezifische Outline-Statistik-Zeile prüfen
    outline_log = [r for r in caplog.records if "Outline" in r.message]
    assert len(outline_log) >= 1, "Mindestens eine Log-Zeile über Outline-Statistik erwartet"


def test_transform_to_gold_uses_correct_source_type() -> None:
    """Gold-Records müssen source_type == 'modulbeschreibung' haben."""
    rows = [_make_silver_row("modul_a"), _make_silver_row("modul_b")]
    df = pd.DataFrame(rows)
    records = transform_to_gold(df)

    assert len(records) == 2
    for record in records:
        assert record["source_type"] == "modulbeschreibung", (
            f"source_type muss 'modulbeschreibung' sein, war '{record['source_type']}'"
        )
        # Schema-Vollständigkeit prüfen
        assert "doc_id" in record
        assert "metadata" in record
        assert "content" in record
        assert "images" in record
        assert "outline" in record["content"]
        assert isinstance(record["content"]["outline"], list)
        assert "pages" in record["content"]
        assert isinstance(record["content"]["pages"], list)


def test_transform_to_gold_includes_pages() -> None:
    """Gold-Records müssen content.pages als Liste von Seiten-Dicts enthalten."""
    rows = [_make_silver_row("modul_a")]
    df = pd.DataFrame(rows)
    records = transform_to_gold(df)

    assert len(records) == 1
    content = records[0]["content"]
    assert "pages" in content
    assert isinstance(content["pages"], list)
    assert len(content["pages"]) == 1
    page = content["pages"][0]
    assert "page_number" in page
    assert "text" in page
