"""V4 Chunker mit Position-aware Bildintegration.

V4 = V2-Architektur + Multimodalität.

Für die meisten Quellen identisch zu V2. Nur das Dokument
"Schulungsunterlagen Auftrag Einsteiger.pdf" wird mit Bildbeschreibungen
angereichert: Pro Seite werden die Bilder lokalisiert und ihre VLM-
Beschreibungen aus dem Cache an der jeweiligen Position im Text eingefügt.

Format der Einfügung: [Bild: <vlm_description>]

Quelle: vereinfachtes MMORE-Pattern (Sallinen et al., 2025).
"""

import json
import logging
from pathlib import Path

import fitz  # PyMuPDF

from rag.config import (
    V4_IMAGE_DESCRIPTIONS_CACHE,
    V4_IMAGE_MARKER_TEMPLATE,
    V4_KEYWORDS_CACHE,
    V4_SCHULUNG_PDF_NAME,
    V4_VLM_SOURCE_PDF,
)
from rag.index.chunking_v2 import _enrich_with_metadata, chunk_documents_v2
from rag.index.keyword_generator import enrich_with_keywords

logger = logging.getLogger(__name__)


def _load_image_descriptions_cache(
    cache_path: Path = V4_IMAGE_DESCRIPTIONS_CACHE,
) -> dict[str, str]:
    """Lädt Cache als Dict image_id → vlm_description."""
    if not cache_path.exists():
        logger.warning("V4 Image-Cache fehlt: %s", cache_path)
        return {}
    cache: dict[str, str] = {}
    with cache_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                cache[entry["image_id"]] = entry["vlm_description"]
    logger.info("V4 Image-Cache geladen: %d Beschreibungen", len(cache))
    return cache


def _build_image_id(page_number: int, image_index: int) -> str:
    """Eindeutige ID analog zu AP-10 (1-basiert)."""
    return f"schulung_auftrag_einsteiger_p{page_number:03d}_img{image_index:02d}"


def _integrate_images_into_page_text(
    page: fitz.Page,
    page_number: int,
    image_descriptions: dict[str, str],
) -> str:
    """Extrahiert Text einer Seite und fügt Bildbeschreibungen an Position ein.

    Verwendet PyMuPDF Bounding-Box-Informationen, um Text- und Bildelemente
    räumlich zu sortieren (Top-down nach y-Position). Bilder ohne Cache-Eintrag
    werden übersprungen.

    Args:
        page: Bereits geöffnete fitz.Page.
        page_number: Seitennummer (1-basiert, für Bild-ID-Generierung).
        image_descriptions: Mapping image_id → vlm_description.

    Returns:
        Seitentext mit eingefügten [Bild: ...] Markern.
    """
    elements: list[dict] = []

    # Textblöcke: (x0, y0, x1, y1, text, block_no, block_type)
    for block in page.get_text("blocks"):
        if block[6] == 0:  # text block
            text = block[4].strip()
            if text:
                elements.append({"y": block[1], "content": text})

    # Bilder mit Bounding-Boxen
    for img_idx, img in enumerate(page.get_images(full=True), start=1):
        image_id = _build_image_id(page_number, img_idx)
        if image_id not in image_descriptions:
            continue
        try:
            bbox = page.get_image_bbox(img)
            if bbox.is_empty:
                continue
            marker = V4_IMAGE_MARKER_TEMPLATE.format(
                description=image_descriptions[image_id]
            )
            elements.append({"y": bbox.y0, "content": marker})
        except Exception as exc:
            logger.warning(
                "Bbox für %s nicht ermittelbar: %s", image_id, exc
            )

    elements.sort(key=lambda e: e["y"])
    return "\n\n".join(e["content"] for e in elements)


def chunk_schulungsunterlage_v4_with_images(
    schulung_entry: dict,
    image_descriptions: dict[str, str],
    pdf_path: Path,
) -> list[dict]:
    """Chunked das V4-Schulungsunterlagen-PDF mit Bildintegration.

    Pro Seite ein Chunk. Der Chunk-Text enthält den Seitentext mit
    Bildbeschreibungen an der räumlichen Position der jeweiligen Bilder.

    Args:
        schulung_entry: Gold-Eintrag für das V4-PDF.
        image_descriptions: Cache mit Bildbeschreibungen.
        pdf_path: Pfad zur PDF.

    Returns:
        Liste von Chunk-Dicts im V1-kompatiblen Format.
    """
    doc_id = schulung_entry.get("doc_id", "schulungsunterlagen_auftrag_einsteiger")
    source_file = schulung_entry.get("metadata", {}).get("filename", "")
    pages = schulung_entry.get("content", {}).get("pages", [])

    if not pages:
        logger.warning("Keine Seiten im Schulungsunterlagen-Eintrag: %s", doc_id)
        return []

    chunks: list[dict] = []
    doc = fitz.open(pdf_path)
    try:
        for chunk_idx, page_data in enumerate(pages):
            page_number: int = page_data["page_number"]
            fitz_page = doc[page_number - 1]

            enriched_text = _integrate_images_into_page_text(
                fitz_page, page_number, image_descriptions
            )
            if not enriched_text.strip():
                continue

            chunks.append(
                {
                    "id": f"schulungsunterlage__{doc_id}_page_{page_number:04d}",
                    "text": enriched_text,
                    "metadata": {
                        "source_type": "schulungsunterlage",
                        "source_file": source_file,
                        "chunk_index": chunk_idx,
                        "chunking_strategy": "page_v4",
                        "page_number": page_number,
                    },
                }
            )
    finally:
        doc.close()

    logger.info(
        "V4 Schulungsunterlagen-Chunks erstellt: %d (von %d Seiten)",
        len(chunks),
        len(pages),
    )
    return chunks


def chunk_documents_v4(entries: list[dict]) -> list[dict]:
    """V4-Chunker: V2-Architektur + Multimodalität für ein Dokument.

    Alle Quellen ausser "Schulungsunterlagen Auftrag Einsteiger.pdf" werden
    identisch zu V2 verarbeitet. Für das V4-Dokument werden Bildbeschreibungen
    aus dem Cache in den Chunk-Text integriert.

    Args:
        entries: Gold-Schicht-Einträge (alle Quellen).

    Returns:
        Liste von Chunks mit V2-Metadaten plus V4-Bildanreicherung.
    """
    image_descriptions = _load_image_descriptions_cache()

    v4_schulung_entries: list[dict] = []
    other_entries: list[dict] = []

    for entry in entries:
        source_type = entry.get("source_type", "")
        filename = entry.get("metadata", {}).get("filename", "")
        if source_type == "schulungsunterlage" and filename == V4_SCHULUNG_PDF_NAME:
            v4_schulung_entries.append(entry)
        else:
            other_entries.append(entry)

    logger.info(
        "V4-Chunking: %d V4-Schulungsunterlage-Einträge, %d andere",
        len(v4_schulung_entries),
        len(other_entries),
    )

    # V2-Chunking für alle anderen Quellen
    chunks_others = chunk_documents_v2(other_entries)

    # V4-spezifisches Chunking für die Schulungsunterlage
    chunks_v4_schulung: list[dict] = []
    for entry in v4_schulung_entries:
        entry_chunks = chunk_schulungsunterlage_v4_with_images(
            entry, image_descriptions, V4_VLM_SOURCE_PDF
        )
        entry_chunks = _enrich_with_metadata(entry_chunks, [entry])
        entry_chunks = enrich_with_keywords(
            entry_chunks, cache_path=V4_KEYWORDS_CACHE
        )
        chunks_v4_schulung.extend(entry_chunks)

    all_chunks = chunks_others + chunks_v4_schulung
    logger.info("V4-Chunking abgeschlossen: %d Chunks total", len(all_chunks))
    return all_chunks
