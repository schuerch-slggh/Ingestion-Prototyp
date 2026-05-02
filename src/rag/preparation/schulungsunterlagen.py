"""Schulungsunterlagen-Datenaufbereitung: Bronze → Silver → Gold."""

import json
import logging
import random
from pathlib import Path

import pandas as pd

from rag.config import GOLD_DIR, PROJECT_ROOT, RANDOM_SEED
from rag.preparation.pdf_reader import read_pdf, remove_boilerplate

logger = logging.getLogger(__name__)


def load_bronze(
    source_dir: Path, sample_size: int | None = None
) -> list[dict]:
    """Lädt alle PDFs aus dem Quellverzeichnis (flach, keine Unterordner).

    Bilder werden direkt in GOLD_DIR/images/<doc_id>/ abgelegt.

    Args:
        source_dir: Verzeichnis mit den Schulungsunterlagen-PDFs.
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

    Entfernt Boilerplate aus full_text. Outline wird mitgeführt (bei
    Schulungsunterlagen in der Regel leer). Speichert pro-Seite-Text in
    pages_json für späteres V1-Chunking.

    Args:
        documents: Liste von Dicts aus load_bronze.

    Returns:
        DataFrame mit den Spalten:
        doc_id, filename, page_count, full_text, outline_json,
        pages_json, images_json, image_count.
    """
    rows = []
    total_pages = 0
    total_images = 0

    for doc in documents:
        outline = doc.get("outline", [])
        images = doc.get("images", [])

        cleaned_pages = [
            {"page_number": p["page_number"], "text": remove_boilerplate(p["text"])}
            for p in doc.get("pages", [])
        ]
        cleaned_text = "\n\n".join(p["text"] for p in cleaned_pages if p["text"]).strip()

        total_pages += doc["page_count"]
        total_images += len(images)

        rows.append({
            "doc_id": doc["doc_id"],
            "filename": doc["filename"],
            "page_count": doc["page_count"],
            "full_text": cleaned_text,
            "outline_json": json.dumps(outline, ensure_ascii=False),
            "pages_json": json.dumps(cleaned_pages, ensure_ascii=False),
            "images_json": json.dumps(images, ensure_ascii=False),
            "image_count": len(images),
        })

    df = pd.DataFrame(rows)
    logger.info(
        "Silver bereinigt: %d Dokumente, %d Seiten, %d Bilder",
        len(df),
        total_pages,
        total_images,
    )
    return df


def transform_to_gold(df: pd.DataFrame) -> list[dict]:
    """Überführt Silver-Daten in das Gold-JSONL-Format.

    Bild-Pfade werden relativ zum Projektroot gespeichert.

    Args:
        df: Silver-DataFrame aus clean_to_silver.

    Returns:
        Liste von Gold-Dicts mit source_type "schulungsunterlage".
    """
    records = []
    for _, row in df.iterrows():
        outline = json.loads(row["outline_json"])
        pages = json.loads(row["pages_json"])
        images_raw = json.loads(row["images_json"])

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
            "source_type": "schulungsunterlage",
            "metadata": {
                "filename": str(row["filename"]),
                "page_count": int(row["page_count"]),
                "image_count": int(row["image_count"]),
            },
            "content": {
                "full_text": str(row["full_text"]),
                "outline": outline,
                "pages": pages,
            },
            "images": images,
        })

    logger.info("Gold-Records erstellt: %d", len(records))
    return records
