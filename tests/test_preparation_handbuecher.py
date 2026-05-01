"""Tests für die Handbuch-Datenaufbereitung (AP-2c)."""

import json
import struct
import sys
import zlib
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fitz  # PyMuPDF

from rag.preparation.handbuecher import clean_to_silver, transform_to_gold
from rag.preparation.pdf_reader import MIN_IMAGE_SIZE, extract_images, read_pdf_text


# ---------------------------------------------------------------------------
# Hilfsfunktionen für synthetische Test-PDFs
# ---------------------------------------------------------------------------


def _make_png_bytes(width: int, height: int) -> bytes:
    """Erstellt minimale gültige PNG-Bytes mit einfarbigem Inhalt."""

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    row = bytes([0] + [100, 150, 200] * width)
    idat = chunk(b"IDAT", zlib.compress(row * height))
    iend = chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


def _make_pdf_with_toc(tmp_path: Path) -> Path:
    """Erstellt eine Test-PDF mit zwei Seiten und bekannter TOC-Struktur."""
    pdf_path = tmp_path / "toc_test.pdf"
    doc = fitz.open()
    p1 = doc.new_page(width=400, height=600)
    p1.insert_text((50, 100), "Inhalt von Kapitel Eins")
    p2 = doc.new_page(width=400, height=600)
    p2.insert_text((50, 100), "Inhalt von Kapitel Zwei")
    doc.set_toc([
        [1, "Kapitel Eins", 1],
        [2, "Unterkapitel 1.1", 1],
        [1, "Kapitel Zwei", 2],
    ])
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _make_pdf_with_images(tmp_path: Path) -> Path:
    """Erstellt eine Test-PDF mit einem grossen (100x100) und einem kleinen (30x30) Bild."""
    base_path = tmp_path / "images_base.pdf"
    final_path = tmp_path / "images_test.pdf"

    # Schritt 1: Basis-PDF erstellen
    doc = fitz.open()
    doc.new_page(width=400, height=600)
    doc.save(str(base_path))
    doc.close()

    # Schritt 2: Bilder einfügen (zweistufig wegen PyMuPDF-Eigenheit)
    doc = fitz.open(str(base_path))
    page = doc[0]
    large_png = _make_png_bytes(100, 100)
    small_png = _make_png_bytes(30, 30)
    page.insert_image(fitz.Rect(100, 100, 300, 300), stream=large_png)
    page.insert_image(fitz.Rect(10, 10, 20, 20), stream=small_png)
    doc.save(str(final_path))
    doc.close()
    return final_path


def _make_silver_df(n: int = 2) -> pd.DataFrame:
    """Erstellt einen minimalen Silver-DataFrame für transform_to_gold-Tests."""
    return pd.DataFrame({
        "doc_id": [f"handbuch_test_{i}" for i in range(1, n + 1)],
        "filename": [f"Handbuch Test {i}.pdf" for i in range(1, n + 1)],
        "page_count": [10] * n,
        "full_text": [f"Volltext Handbuch {i}" for i in range(1, n + 1)],
        "outline_json": [
            json.dumps([{"level": 1, "title": "Kap 1", "page": 1}])
        ] * n,
        "images_json": [
            json.dumps([{
                "image_id": "img_001",
                "page": 1,
                "filepath": f"/project/data/gold/images/handbuch_test_{idx}/img_001.png",
                "width": 100,
                "height": 100,
            }])
            for idx in range(1, n + 1)
        ],
        "image_count": [1] * n,
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_read_pdf_text_extracts_outline(tmp_path: Path) -> None:
    """read_pdf_text muss die TOC-Struktur der PDF korrekt auslesen."""
    pdf_path = _make_pdf_with_toc(tmp_path)
    result = read_pdf_text(pdf_path)

    assert result["page_count"] == 2
    assert len(result["outline"]) == 3

    levels = [e["level"] for e in result["outline"]]
    titles = [e["title"] for e in result["outline"]]
    assert levels == [1, 2, 1]
    assert "Kapitel Eins" in titles
    assert "Kapitel Zwei" in titles
    assert "Unterkapitel 1.1" in titles

    assert "doc_id" in result
    assert "full_text" in result
    assert result["full_text"] != ""


def test_extract_images_skips_small_images(tmp_path: Path) -> None:
    """extract_images muss Bilder unter MIN_IMAGE_SIZE x MIN_IMAGE_SIZE verwerfen."""
    pdf_path = _make_pdf_with_images(tmp_path)
    out_dir = tmp_path / "images"
    doc_id = "test_doc"

    records = extract_images(pdf_path, out_dir, doc_id)

    assert len(records) == 1, (
        f"Erwartet 1 Bild (gross), gefunden {len(records)}. "
        f"MIN_IMAGE_SIZE={MIN_IMAGE_SIZE}"
    )
    assert records[0]["width"] >= MIN_IMAGE_SIZE
    assert records[0]["height"] >= MIN_IMAGE_SIZE

    img_file = Path(records[0]["filepath"])
    assert img_file.exists(), f"PNG-Datei wurde nicht erstellt: {img_file}"
    assert img_file.suffix == ".png"


def test_clean_to_silver_removes_boilerplate() -> None:
    """clean_to_silver muss Boilerplate-Zeilen (Seitenzahlen, Copyright) entfernen."""
    raw_text = (
        "Einleitung\n"
        "42\n"  # isolierte Seitenzahl → muss entfernt werden
        "Dies ist normaler Text.\n"
        "Copyright © 2024 SelectLine Software AG\n"  # → muss entfernt werden
        "Weiterer normaler Text.\n"
        "© 2023 SelectLine\n"  # → muss entfernt werden
        "Abschluss"
    )
    documents = [{
        "doc_id": "handbuch_test",
        "filename": "Test.pdf",
        "page_count": 5,
        "full_text": raw_text,
        "outline": [],
        "images": [],
    }]
    df = clean_to_silver(documents)

    assert len(df) == 1
    cleaned = df.iloc[0]["full_text"]

    assert "42" not in cleaned.splitlines(), "Isolierte Seitenzahl muss entfernt werden"
    assert "Copyright" not in cleaned, "Copyright-Zeile muss entfernt werden"
    assert "© 2023" not in cleaned, "© YYYY-Zeile muss entfernt werden"
    assert "normaler Text" in cleaned, "Normaler Text muss erhalten bleiben"
    assert "Einleitung" in cleaned


def test_transform_to_gold_produces_correct_schema() -> None:
    """transform_to_gold muss das dokumentierte Gold-Schema einhalten."""
    df = _make_silver_df(2)
    records = transform_to_gold(df)

    assert len(records) == 2
    for i, record in enumerate(records, start=1):
        assert record["source_type"] == "handbuch"
        assert record["doc_id"] == f"handbuch_test_{i}"

        meta = record["metadata"]
        assert "filename" in meta
        assert "page_count" in meta
        assert "image_count" in meta
        assert isinstance(meta["page_count"], int)

        content = record["content"]
        assert "full_text" in content
        assert "outline" in content
        assert isinstance(content["outline"], list)

        assert "images" in record
        assert isinstance(record["images"], list)
        assert len(record["images"]) == 1

        img = record["images"][0]
        assert "image_id" in img
        assert "page" in img
        assert "filepath" in img
        assert "width" in img
        assert "height" in img
        assert "\\" not in img["filepath"], "Pfad muss Forward-Slashes verwenden"
