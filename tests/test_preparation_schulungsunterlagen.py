"""Tests für die Schulungsunterlagen-Datenaufbereitung (AP-2e)."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.preparation.schulungsunterlagen import clean_to_silver, transform_to_gold


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _make_doc(
    doc_id: str = "schulung_test",
    pages: list[dict] | None = None,
) -> dict:
    """Erstellt ein minimales synthetisches Dokument-Dict."""
    if pages is None:
        pages = [
            {"page_number": 1, "text": "Seite eins Inhalt."},
            {"page_number": 2, "text": "Seite zwei Inhalt."},
        ]
    return {
        "doc_id": doc_id,
        "filename": f"{doc_id}.pdf",
        "page_count": len(pages),
        "full_text": " ".join(p["text"] for p in pages),
        "outline": [],
        "images": [],
        "pages": pages,
    }


def _make_silver_row(doc_id: str = "schulung_test") -> dict:
    """Erstellt eine Silver-DataFrame-Zeile."""
    pages = [{"page_number": 1, "text": "Seitentext der Schulung"}]
    return {
        "doc_id": doc_id,
        "filename": f"{doc_id}.pdf",
        "page_count": 1,
        "full_text": "Seitentext der Schulung",
        "outline_json": json.dumps([]),
        "pages_json": json.dumps(pages),
        "images_json": json.dumps([]),
        "image_count": 0,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_transform_to_gold_uses_correct_source_type() -> None:
    """Gold-Records müssen source_type == 'schulungsunterlage' haben."""
    rows = [_make_silver_row("schulung_a"), _make_silver_row("schulung_b")]
    df = pd.DataFrame(rows)
    records = transform_to_gold(df)

    assert len(records) == 2
    for record in records:
        assert record["source_type"] == "schulungsunterlage", (
            f"source_type muss 'schulungsunterlage' sein, war '{record['source_type']}'"
        )


def test_transform_to_gold_includes_pages() -> None:
    """Gold-Records müssen content.pages als Liste von Seiten-Dicts enthalten."""
    rows = [_make_silver_row("schulung_a")]
    df = pd.DataFrame(rows)
    records = transform_to_gold(df)

    assert len(records) == 1
    content = records[0]["content"]
    assert "pages" in content, "content muss pages-Array enthalten"
    assert isinstance(content["pages"], list)
    assert len(content["pages"]) == 1
    page = content["pages"][0]
    assert "page_number" in page
    assert "text" in page


def test_clean_to_silver_pages_consistent_with_full_text() -> None:
    """pages[*].text und full_text müssen konsistent (aus denselben bereinigten Seiten) sein."""
    doc = _make_doc(pages=[
        {"page_number": 1, "text": "Inhalt Seite eins.\n42\nWeiterer Text."},
        {"page_number": 2, "text": "Inhalt Seite zwei."},
    ])
    df = clean_to_silver([doc])

    assert len(df) == 1
    pages = json.loads(df.iloc[0]["pages_json"])
    full_text = df.iloc[0]["full_text"]

    # full_text muss aus den bereinigten Seiten zusammengesetzt sein
    joined = "\n\n".join(p["text"] for p in pages if p["text"]).strip()
    assert full_text == joined, "full_text muss aus den bereinigten pages-Texten zusammengesetzt sein"

    # Boilerplate (isolierte Seitenzahl) muss in beiden entfernt sein
    assert "42" not in full_text.splitlines()
    for page in pages:
        assert "42" not in page["text"].splitlines()
