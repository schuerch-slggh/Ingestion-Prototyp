"""Tests für den V4-Chunker mit Position-aware Bildintegration (AP-11)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.index.chunking_v4 import (
    _build_image_id,
    _load_image_descriptions_cache,
    chunk_documents_v4,
    chunk_schulungsunterlage_v4_with_images,
)

# ── Fixtures: Keyword-Generator deaktivieren ─────────────────────────────────


@pytest.fixture(autouse=True)
def mock_keyword_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deaktiviert LLM-Calls in allen V4-Tests."""

    def _stub(chunks: list[dict], cache_path: object = None) -> list[dict]:
        for c in chunks:
            c["metadata"]["keywords"] = "kw_a,kw_b"
        return chunks

    monkeypatch.setattr("rag.index.chunking_v4.enrich_with_keywords", _stub)
    monkeypatch.setattr("rag.index.chunking_v2.enrich_with_keywords", _stub)


# ── Hilfsfunktion: minimaler Gold-Eintrag ────────────────────────────────────


def _make_v4_entry(pages: list[dict] | None = None) -> dict:
    return {
        "doc_id": "schulungsunterlagen_auftrag_einsteiger",
        "source_type": "schulungsunterlage",
        "metadata": {
            "filename": "Schulungsunterlagen Auftrag Einsteiger.pdf",
            "page_count": len(pages or []),
            "image_count": 0,
        },
        "content": {
            "full_text": "",
            "outline": [],
            "pages": pages or [{"page_number": 1, "text": "Seite 1"}],
        },
        "images": [],
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_build_image_id_format() -> None:
    """ID-Format ist korrekt und zero-padded."""
    assert _build_image_id(42, 1) == "schulung_auftrag_einsteiger_p042_img01"
    assert _build_image_id(1, 10) == "schulung_auftrag_einsteiger_p001_img10"


def test_load_image_descriptions_cache_empty(tmp_path: Path) -> None:
    """Cache ist leer wenn Datei nicht existiert."""
    cache = _load_image_descriptions_cache(tmp_path / "nonexistent.jsonl")
    assert cache == {}


def test_load_image_descriptions_cache_with_entries(tmp_path: Path) -> None:
    """Cache lädt JSONL-Einträge korrekt."""
    cache_file = tmp_path / "test.jsonl"
    cache_file.write_text(
        json.dumps(
            {
                "image_id": "schulung_auftrag_einsteiger_p001_img01",
                "vlm_description": "Test description",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cache = _load_image_descriptions_cache(cache_file)
    assert "schulung_auftrag_einsteiger_p001_img01" in cache
    assert cache["schulung_auftrag_einsteiger_p001_img01"] == "Test description"


def test_chunk_v4_with_images_inserts_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V4-Chunker fügt [Bild: ...] Marker in den Text ein."""
    import fitz

    # Minimale 1-seitige Test-PDF
    tmp_pdf = tmp_path / "test.pdf"
    doc = fitz.Document()
    doc.new_page()
    doc.save(str(tmp_pdf))
    doc.close()

    entry = _make_v4_entry([{"page_number": 1, "text": "Original Text"}])
    cache = {"schulung_auftrag_einsteiger_p001_img01": "Test-Bildbeschreibung"}

    monkeypatch.setattr(
        "rag.index.chunking_v4._integrate_images_into_page_text",
        lambda *args, **kwargs: "Original Text\n\n[Bild: Test-Bildbeschreibung]",
    )

    chunks = chunk_schulungsunterlage_v4_with_images(entry, cache, tmp_pdf)

    assert len(chunks) == 1
    assert "[Bild: Test-Bildbeschreibung]" in chunks[0]["text"]
    assert chunks[0]["id"].endswith("_page_0001")
    assert chunks[0]["metadata"]["source_type"] == "schulungsunterlage"


def test_chunk_v4_separates_v4_schulung_from_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V4-Chunker trennt das V4-PDF von anderen Einträgen."""
    monkeypatch.setattr(
        "rag.index.chunking_v4._load_image_descriptions_cache",
        lambda *args: {},
    )
    monkeypatch.setattr(
        "rag.index.chunking_v4.chunk_documents_v2",
        lambda entries: [{"id": "other", "text": "x", "metadata": {}}],
    )
    monkeypatch.setattr(
        "rag.index.chunking_v4.chunk_schulungsunterlage_v4_with_images",
        lambda *args, **kwargs: [{"id": "v4_schulung", "text": "y", "metadata": {}}],
    )
    monkeypatch.setattr(
        "rag.index.chunking_v4._enrich_with_metadata",
        lambda chunks, entries: chunks,
    )

    entries = [
        {
            "source_type": "schulungsunterlage",
            "metadata": {"filename": "Schulungsunterlagen Auftrag Einsteiger.pdf"},
            "doc_id": "schulungsunterlagen_auftrag_einsteiger",
            "content": {"pages": [{"page_number": 1, "text": "Test"}]},
        },
        {
            "source_type": "schulungsunterlage",
            "metadata": {"filename": "Schulungsunterlagen Rechnungswesen.pdf"},
            "doc_id": "schulungsunterlagen_rechnungswesen",
            "content": {"pages": []},
        },
        {
            "source_type": "handbuch",
            "metadata": {"filename": "Auftrag Handbuch.pdf"},
            "doc_id": "handbuch_auftrag",
            "content": {},
        },
    ]

    chunks = chunk_documents_v4(entries)
    chunk_ids = [c["id"] for c in chunks]
    assert "v4_schulung" in chunk_ids
    assert "other" in chunk_ids


def test_v4_image_marker_format() -> None:
    """Format des Marker-Templates ist korrekt."""
    from rag.config import V4_IMAGE_MARKER_TEMPLATE

    result = V4_IMAGE_MARKER_TEMPLATE.format(description="Test")
    assert result == "[Bild: Test]"
