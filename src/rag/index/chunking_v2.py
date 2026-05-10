"""V2-Chunking: V1-Strategien + strukturelle Metadaten + Schlüsselwörter.

V2 = V1 + zwei Post-Processing-Schritte:
    Schritt 1: V1-Chunker liefert Chunks mit V1-Metadaten.
    Schritt 2: Strukturelle Metadaten aus Gold-Eintrag:
               - Forum:             post_id, topic_id, module_lookup, post_date
               - Ticket:            ticket_id, product, category,
                                    version_reported, version_resolved,
                                    processed_date
               - Handbuch:          outline_level, page_start, page_end,
                                    doc_title; outline_path serialisiert
               - Modulbeschreibung: doc_title
               - Schulungsunterlage:doc_title, module_filename (aus doc_id)
    Schritt 3: Schlüsselwort-Anreicherung (gpt-4o-mini, 5–12 pro Chunk).
               Feld: keywords (kommagetrennter String).

Hybrid-Retrieval (Embedding + BM25 + RRF) ist in retriever.py implementiert.
V3 (Recency-Re-Ranking) und V4 (VLM) kommen in späteren APs.
"""

import logging
import re
from pathlib import Path

from rag.index.chunking_v1 import chunk_documents_v1
from rag.index.keyword_generator import enrich_with_keywords

logger = logging.getLogger(__name__)

MIN_MODULE_TOKEN_LENGTH = 3

# Suffix patterns for extracting doc_id from V1 chunk IDs (most specific first)
_SUFFIX_PATTERNS = [
    r"_h[234]_\d{4}_recursive_\d{4}$",
    r"_page_\d{4}_recursive_\d{4}$",
    r"_overflow_recursive_\d{4}$",
    r"_nooutline_recursive_\d{4}$",
    r"_h[234]_\d{4}$",
    r"_page_\d{4}$",
]


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _derive_doc_title(source_file: str) -> str:
    """Wandelt source_file in lesbaren Titel.

    'SelectLine_Auftrag_Handbuch.pdf' → 'SelectLine Auftrag Handbuch'

    Args:
        source_file: Dateiname mit oder ohne Endung.

    Returns:
        Titel ohne Endung, Unterstriche durch Leerzeichen ersetzt.
        Leerer String bei leerem Input.
    """
    if not source_file:
        return ""
    stem = Path(source_file).stem
    return stem.replace("_", " ")


def _derive_module_from_doc_id(doc_id: str) -> str:
    """Extrahiert Modulnamen aus doc_id-Konvention für Schulungsunterlagen.

    'schulungsunterlagen_auftrag_einsteiger' → 'Auftrag'

    Heuristik: Erstes Token nach dem ersten Unterstrich, kapitalisiert.
    Bei fehlendem Unterstrich oder zu kurzem Token: leerer String.

    Args:
        doc_id: Gold-Entry doc_id.

    Returns:
        Modulname (kapitalisiert) oder leerer String.
    """
    if not doc_id or "_" not in doc_id:
        return ""
    token = doc_id.split("_", 1)[1].split("_")[0]
    if len(token) < MIN_MODULE_TOKEN_LENGTH:
        return ""
    return token.capitalize()


def _serialize_outline_path(path: list[str] | str) -> str:
    """Serialisiert outline_path für ChromaDB-Speicherung.

    ChromaDB-Metadaten dürfen keine Listen enthalten. Konvention:
    Trennzeichen ' > '. Beispiel: ['Kapitel 1', 'Abschnitt 1.1']
    → 'Kapitel 1 > Abschnitt 1.1'

    Ist path bereits ein String, wird er unverändert zurückgegeben.

    Args:
        path: Liste der Header-Titel oder bereits serialisierter String.

    Returns:
        Serialisierter String, leerer String falls Eingabe leer.
    """
    if isinstance(path, str):
        return path
    if not path:
        return ""
    return " > ".join(path)


def _extract_doc_id(chunk_id: str, source_type: str) -> str:
    """Extrahiert doc_id aus V1-Chunk-ID.

    V1-Format: '{source_type}__{doc_id}_{suffix}'.
    Atomic-Format: '{source_type}__{doc_id}' (kein Suffix).

    Args:
        chunk_id: V1-Chunk-ID.
        source_type: Quelltyp (für Präfix-Erkennung).

    Returns:
        Extrahierte doc_id oder leerer String bei nicht-erkennbarem Format.
    """
    prefix = f"{source_type}__"
    if not chunk_id.startswith(prefix):
        return ""
    body = chunk_id[len(prefix):]
    for pattern in _SUFFIX_PATTERNS:
        m = re.search(pattern, body)
        if m:
            return body[: m.start()]
    return body  # atomic: kein Suffix


def _find_section_pages(
    outline: list[dict], path: list[str]
) -> tuple[int, int]:
    """Sucht page_start und page_end für eine Outline-Sektion.

    Matcht das letzte Element von path gegen Outline-Einträge der
    passenden Ebene (level == len(path)).

    Args:
        outline: Outline-Liste aus Gold-Eintrag.
        path: Outline-Pfad aus V1-Chunk-Metadaten.

    Returns:
        (page_start, page_end) — (0, 0) bei nicht gefundener Sektion.
    """
    if not path or not outline:
        return 0, 0
    target_title = path[-1]
    target_level = len(path)
    max_page = max((e["page"] for e in outline), default=0) + 1

    for i, entry in enumerate(outline):
        if entry["level"] == target_level and entry["title"] == target_title:
            page_start = entry["page"]
            page_end = max_page
            for j in range(i + 1, len(outline)):
                if outline[j]["level"] <= target_level:
                    page_end = outline[j]["page"]
                    break
            return page_start, page_end
    return 0, 0


# ── Anreicherungs-Funktionen pro Quelltyp ────────────────────────────────────


def _enrich_forum(chunk_metadata: dict, gold_entry: dict) -> None:
    """Ergänzt Chunk-Metadaten um strukturelle Forum-Felder.

    Modifiziert chunk_metadata in-place. Felder werden als leerer String
    gesetzt, wenn im Gold-Eintrag nicht vorhanden (ChromaDB-Kompatibilität).

    Felder: post_id, topic_id, module_lookup, post_date.
    """
    meta = gold_entry.get("metadata", {})
    chunk_metadata["post_id"] = str(meta.get("post_id") or "")
    chunk_metadata["topic_id"] = str(meta.get("topic_id") or "")
    chunk_metadata["module_lookup"] = str(meta.get("module") or "")
    chunk_metadata["post_date"] = str(meta.get("post_date") or "")


def _enrich_ticket(chunk_metadata: dict, gold_entry: dict) -> None:
    """Ergänzt Chunk-Metadaten um strukturelle Ticket-Felder.

    Felder: ticket_id, product, category, version_reported,
            version_resolved, processed_date.
    """
    meta = gold_entry.get("metadata", {})
    chunk_metadata["ticket_id"] = str(meta.get("ticket_id") or "")
    chunk_metadata["product"] = str(meta.get("product") or "")
    chunk_metadata["category"] = str(meta.get("category") or "")
    chunk_metadata["version_reported"] = str(meta.get("version_reported") or "")
    chunk_metadata["version_resolved"] = str(meta.get("version_resolved") or "")
    chunk_metadata["processed_date"] = str(meta.get("processed_date") or "")


def _enrich_handbuch(chunk_metadata: dict, gold_entry: dict) -> None:
    """Ergänzt Chunk-Metadaten um strukturelle Handbuch-Felder.

    Serialisiert outline_path von Liste zu String. Leitet outline_level
    aus Länge von outline_path ab. Sucht page_start / page_end aus
    dem Gold-Outline.

    Felder: outline_level, page_start, page_end, doc_title;
            outline_path wird serialisiert.
    """
    source_file = chunk_metadata.get("source_file", "")
    outline_path = chunk_metadata.get("outline_path", [])
    outline = gold_entry.get("content", {}).get("outline", [])

    # Outline-Level aus Pfad-Länge ableiten (vor Serialisierung)
    if isinstance(outline_path, list):
        outline_level = len(outline_path)
        page_start, page_end = _find_section_pages(outline, outline_path)
    else:
        # Bereits serialisiert (sollte bei V1-Input nicht vorkommen)
        logger.warning(
            "outline_path für Chunk bereits serialisiert: %r", outline_path
        )
        outline_level = outline_path.count(" > ") + 1 if outline_path else 0
        page_start, page_end = 0, 0

    chunk_metadata["outline_level"] = outline_level
    chunk_metadata["page_start"] = page_start
    chunk_metadata["page_end"] = page_end
    chunk_metadata["doc_title"] = _derive_doc_title(source_file)
    chunk_metadata["outline_path"] = _serialize_outline_path(outline_path)


def _enrich_modulbeschreibung(chunk_metadata: dict, gold_entry: dict) -> None:
    """Ergänzt Chunk-Metadaten um doc_title für Modulbeschreibungen."""
    source_file = chunk_metadata.get("source_file", "")
    chunk_metadata["doc_title"] = _derive_doc_title(source_file)


def _enrich_schulungsunterlage(
    chunk_metadata: dict, gold_entry: dict
) -> None:
    """Ergänzt Chunk-Metadaten um doc_title und module_filename.

    module_filename heuristisch aus doc_id abgeleitet: erstes Token nach
    dem ersten Unterstrich, z. B. 'schulungsunterlagen_auftrag' → 'Auftrag'.
    """
    source_file = chunk_metadata.get("source_file", "")
    doc_id = gold_entry.get("doc_id", "")
    chunk_metadata["doc_title"] = _derive_doc_title(source_file)
    chunk_metadata["module_filename"] = _derive_module_from_doc_id(doc_id)


_ENRICHERS = {
    "forum": _enrich_forum,
    "ticket": _enrich_ticket,
    "handbuch": _enrich_handbuch,
    "modulbeschreibung": _enrich_modulbeschreibung,
    "schulungsunterlage": _enrich_schulungsunterlage,
}


# ── Anreicherungs-Hauptfunktion ───────────────────────────────────────────────


def _enrich_with_metadata(
    chunks: list[dict],
    gold_entries: list[dict],
) -> list[dict]:
    """Reichert V1-Chunks um strukturelle Metadaten aus den Gold-Einträgen an.

    Mapping Chunk → Gold-Eintrag über doc_id im Chunk-ID.
    Alle Chunks eines Gold-Eintrags erhalten dieselben strukturellen
    Metadaten (Recursive-Fallback-Sub-Chunks erben Parent-Metadaten).

    Args:
        chunks: V1-Chunks (Output von chunk_documents_v1).
        gold_entries: Original-Gold-Einträge zur Metadaten-Extraktion.

    Returns:
        Angereicherte Chunks (gleiche Reihenfolge wie Input).
    """
    gold_by_doc_id = {e["doc_id"]: e for e in gold_entries}
    enriched_counts: dict[str, int] = {}
    missing: list[str] = []

    for chunk in chunks:
        source_type = chunk["metadata"].get("source_type", "")
        enricher = _ENRICHERS.get(source_type)
        if enricher is None:
            continue

        doc_id = _extract_doc_id(chunk["id"], source_type)
        gold_entry = gold_by_doc_id.get(doc_id)
        if gold_entry is None:
            missing.append(chunk["id"])
            continue

        enricher(chunk["metadata"], gold_entry)
        enriched_counts[source_type] = enriched_counts.get(source_type, 0) + 1

    for st, count in enriched_counts.items():
        logger.debug("Angereichert [%s]: %d Chunks", st, count)

    if missing:
        logger.warning(
            "%d Chunks ohne Gold-Eintrag (doc_id nicht auflösbar): %s …",
            len(missing),
            missing[:3],
        )

    return chunks


# ── Hauptfunktion ─────────────────────────────────────────────────────────────


def chunk_documents_v2(gold_entries: list[dict]) -> list[dict]:
    """V2-Chunking: V1-Strategien + strukturelle Metadaten + Schlüsselwörter.

    Args:
        gold_entries: Liste von Gold-Eintrag-Dicts (eingelesen aus JSONL).

    Returns:
        Liste von Chunk-Dicts mit den Schlüsseln 'id', 'text', 'metadata'.
        Schnittstelle identisch zu V0 / V1.
    """
    logger.info("V2-Chunking gestartet: %d Gold-Einträge", len(gold_entries))
    chunks = chunk_documents_v1(gold_entries)
    chunks = _enrich_with_metadata(chunks, gold_entries)
    chunks = enrich_with_keywords(chunks)
    logger.info("V2-Chunking abgeschlossen: %d Chunks", len(chunks))
    return chunks
