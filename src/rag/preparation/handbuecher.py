"""Handbuch-Datenaufbereitung: Bronze → Silver → Gold."""

import json
import logging
import random
import re
from pathlib import Path

import pandas as pd

from rag.config import GOLD_DIR, PROJECT_ROOT, RANDOM_SEED
from rag.preparation.pdf_reader import read_pdf

logger = logging.getLogger(__name__)

# Boilerplate-Pattern (zeilenweise geprüft)
_BOILERPLATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\d+$"),                            # isolierte Seitenzahlen
    re.compile(r"^Copyright\s+©", re.IGNORECASE),    # Copyright-Zeilen
    re.compile(r"^©\s*\d{4}", re.IGNORECASE),        # © YYYY ...
]


def _remove_boilerplate(text: str) -> str:
    """Entfernt Boilerplate-Zeilen (Seitenzahlen, Copyright) aus dem Text."""
    lines = text.splitlines()
    cleaned = [
        line
        for line in lines
        if not any(pat.match(line.strip()) for pat in _BOILERPLATE_PATTERNS)
    ]
    return "\n".join(cleaned).strip()


def load_bronze(
    source_dir: Path, sample_size: int | None = None
) -> list[dict]:
    """Lädt alle PDFs aus dem Quellverzeichnis und extrahiert Text, Outline und Bilder.

    Bilder werden dabei direkt in GOLD_DIR/images/<doc_id>/ abgelegt.

    Args:
        source_dir: Verzeichnis mit den Handbuch-PDFs.
        sample_size: Bei Angabe reproduzierbare Stichprobe dieser Anzahl Dokumente.

    Returns:
        Liste von Dicts (je PDF ein Dict aus read_pdf).
    """
    pdf_files = sorted(source_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("Keine PDFs in %s gefunden.", source_dir)
        return []

    if sample_size is not None:
        rng = random.Random(RANDOM_SEED)
        pdf_files = rng.sample(pdf_files, min(sample_size, len(pdf_files)))
        logger.info(
            "Stichprobe: %d von %d PDFs werden verarbeitet.",
            len(pdf_files),
            len(sorted(source_dir.glob("*.pdf"))),
        )

    image_output_dir = GOLD_DIR / "images"
    documents = []
    for pdf_path in pdf_files:
        logger.info("Lade %s …", pdf_path.name)
        doc = read_pdf(pdf_path, image_output_dir)
        documents.append(doc)

    total_pages = sum(d["page_count"] for d in documents)
    total_images = sum(len(d["images"]) for d in documents)
    logger.info(
        "Bronze geladen: %d PDFs, %d Seiten, %d Bilder extrahiert",
        len(documents),
        total_pages,
        total_images,
    )
    return documents


def clean_to_silver(documents: list[dict]) -> pd.DataFrame:
    """Bereinigt Bronze-Dokumente zu Silver.

    Entfernt Boilerplate aus full_text (Seitenzahlen, Copyright-Zeilen).
    Outline und Bilder werden als JSON-Strings für CSV-Kompatibilität gespeichert.

    Args:
        documents: Liste von Dicts aus load_bronze.

    Returns:
        DataFrame mit den Spalten:
        doc_id, filename, page_count, full_text, outline_json,
        images_json, image_count.
    """
    rows = []
    total_pages = 0
    total_images = 0
    outline_depths: list[int] = []

    for doc in documents:
        cleaned_text = _remove_boilerplate(doc["full_text"])
        outline = doc.get("outline", [])
        images = doc.get("images", [])

        max_depth = max((e["level"] for e in outline), default=0)
        outline_depths.append(max_depth)
        total_pages += doc["page_count"]
        total_images += len(images)

        rows.append({
            "doc_id": doc["doc_id"],
            "filename": doc["filename"],
            "page_count": doc["page_count"],
            "full_text": cleaned_text,
            "outline_json": json.dumps(outline, ensure_ascii=False),
            "images_json": json.dumps(images, ensure_ascii=False),
            "image_count": len(images),
        })

    df = pd.DataFrame(rows)
    avg_depth = sum(outline_depths) / len(outline_depths) if outline_depths else 0
    logger.info(
        "Silver bereinigt: %d Dokumente, %d Seiten, %d Bilder, "
        "Ø Outline-Tiefe %.1f",
        len(df),
        total_pages,
        total_images,
        avg_depth,
    )
    return df


def transform_to_gold(df: pd.DataFrame) -> list[dict]:
    """Überführt Silver-Daten in das Gold-JSONL-Format.

    Bild-Pfade werden relativ zum Projektroot gespeichert.

    Args:
        df: Silver-DataFrame aus clean_to_silver.

    Returns:
        Liste von Gold-Dicts mit dem dokumentierten Schema.
    """
    records = []
    for _, row in df.iterrows():
        outline = json.loads(row["outline_json"])
        images_raw = json.loads(row["images_json"])

        # Absolute Pfade → relativ zum Projektroot
        images = []
        for img in images_raw:
            try:
                rel = Path(img["filepath"]).relative_to(PROJECT_ROOT)
                filepath = str(rel).replace("\\", "/")
            except ValueError:
                filepath = img["filepath"]
            images.append({**img, "filepath": filepath})

        records.append({
            "doc_id": str(row["doc_id"]),
            "source_type": "handbuch",
            "metadata": {
                "filename": str(row["filename"]),
                "page_count": int(row["page_count"]),
                "image_count": int(row["image_count"]),
            },
            "content": {
                "full_text": str(row["full_text"]),
                "outline": outline,
            },
            "images": images,
        })

    logger.info("Gold-Records erstellt: %d", len(records))
    return records
