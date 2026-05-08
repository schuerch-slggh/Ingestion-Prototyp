"""V1-Chunking: quellenspezifisches Schneiden je Quelltyp.

V1-Strategie:
    forum, ticket:                  atomar (1 Chunk pro Eintrag)
    modulbeschreibung,
    schulungsunterlage:             seitenweise (1 Chunk pro Seite)
    handbuch:                       outline-basiert auf H2

Bei Token-Überlauf eines Outline- oder Seiten-Chunks erfolgt ein
Fallback auf Recursive-Splitting (1500 Tokens, 100 Overlap).
"""

import logging

import tiktoken

from rag.index.chunking import _split_text

logger = logging.getLogger(__name__)

_ENCODING = tiktoken.get_encoding("cl100k_base")

V1_TOKEN_LIMIT = 2000
V1_ATOMIC_TOKEN_LIMIT = 8000
V1_RECURSIVE_FALLBACK_SIZE = 1500
V1_RECURSIVE_FALLBACK_OVERLAP = 100


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _token_count(text: str) -> int:
    return len(_ENCODING.encode(text))


def _extract_pages_text(pages_by_num: dict[int, str], start: int, end: int) -> str:
    """Konkateniert Seiten von start (inkl.) bis end (exkl.)."""
    parts = [pages_by_num.get(n, "").strip() for n in range(start, end)]
    return "\n".join(p for p in parts if p)


def _make_recursive_chunks(
    text: str,
    source_type: str,
    doc_id: str,
    source_file: str,
    parent_id: str,
    extra_meta: dict,
    start_idx: int = 0,
) -> list[dict]:
    """Recursive-Fallback: zerlegt text und gibt Chunk-Liste zurück."""
    sub_texts = _split_text(
        text, V1_RECURSIVE_FALLBACK_SIZE, V1_RECURSIVE_FALLBACK_OVERLAP
    )
    return [
        {
            "id": f"{source_type}__{doc_id}_{parent_id}_recursive_{start_idx + i:04d}",
            "text": sub,
            "metadata": {
                "source_type": source_type,
                "source_file": source_file,
                "chunk_index": start_idx + i,
                "chunking_strategy": "recursive_fallback",
                **extra_meta,
            },
        }
        for i, sub in enumerate(sub_texts)
    ]


# ── Strategie-Funktionen ─────────────────────────────────────────────────────


def _chunk_atomic(entry: dict, source_type: str) -> list[dict]:
    """Atomares Chunking: 1 Chunk pro Eintrag.

    Bei full_text > 8000 Tokens Fallback auf Recursive.
    """
    doc_id = entry["doc_id"]
    source_file = entry.get("metadata", {}).get("filename", "unknown")
    full_text = entry["content"]["full_text"]

    if _token_count(full_text) <= V1_ATOMIC_TOKEN_LIMIT:
        return [
            {
                "id": f"{source_type}__{doc_id}",
                "text": full_text,
                "metadata": {
                    "source_type": source_type,
                    "source_file": source_file,
                    "chunk_index": 0,
                    "chunking_strategy": "atomic",
                },
            }
        ]

    logger.warning(
        "Atomarer Überlauf in %s (%s) – Recursive-Fallback", doc_id, source_type
    )
    return _make_recursive_chunks(
        full_text, source_type, doc_id, source_file, "overflow", {}
    )


def _chunk_pages(entry: dict, source_type: str) -> list[dict]:
    """Seitenweise: 1 Chunk pro Seite.

    Leere Seiten werden übersprungen. Seiten > 2000 Tokens werden
    via Recursive-Fallback weiter geteilt.
    """
    doc_id = entry["doc_id"]
    source_file = entry.get("metadata", {}).get("filename", "unknown")
    pages = entry["content"].get("pages", [])

    chunks: list[dict] = []
    chunk_idx = 0

    for page in pages:
        page_num: int = page["page_number"]
        text: str = page.get("text", "").strip()
        if not text:
            continue

        page_parent = f"page_{page_num:04d}"

        if _token_count(text) <= V1_TOKEN_LIMIT:
            chunks.append(
                {
                    "id": f"{source_type}__{doc_id}_{page_parent}",
                    "text": text,
                    "metadata": {
                        "source_type": source_type,
                        "source_file": source_file,
                        "chunk_index": chunk_idx,
                        "chunking_strategy": "page",
                        "page_number": page_num,
                    },
                }
            )
            chunk_idx += 1
        else:
            logger.debug(
                "Seite %d in %s > %d Tokens – Recursive-Fallback",
                page_num, doc_id, V1_TOKEN_LIMIT,
            )
            recursive = _make_recursive_chunks(
                text, source_type, doc_id, source_file, page_parent,
                {"page_number": page_num}, start_idx=chunk_idx,
            )
            chunks.extend(recursive)
            chunk_idx += len(recursive)

    return chunks


def _get_h3_sections(
    outline: list[dict], h2_start: int, h2_end: int
) -> list[dict]:
    """Gibt H3-Sektionen (mit page-Ranges) innerhalb einer H2-Section zurück."""
    h3s = [
        item for item in outline
        if item["level"] == 3 and h2_start <= item["page"] < h2_end
    ]
    sections = []
    for i, h3 in enumerate(h3s):
        end = h2_end
        # Nächste H3 (oder höher) innerhalb des H2-Bereichs bestimmt das Ende
        for j in range(i + 1, len(h3s)):
            end = h3s[j]["page"]
            break
        sections.append({"title": h3["title"], "start": h3["page"], "end": end})
    return sections


def _chunk_outline(entry: dict, source_type: str) -> list[dict]:
    """Outline-basiertes Chunking: schneidet entlang H2-Granularität.

    Bei H2 > 2000 Tokens: Fallback auf H3-Granularität für diesen Bereich.
    Bei H3 > 2000 Tokens: Fallback auf Recursive.
    Kein Outline vorhanden: kompletter Recursive-Fallback auf full_text.
    """
    doc_id = entry["doc_id"]
    source_file = entry.get("metadata", {}).get("filename", "unknown")
    content = entry["content"]
    outline: list[dict] = content.get("outline", [])
    pages: list[dict] = content.get("pages", [])

    if not outline or not pages:
        logger.warning("Kein Outline/Pages in %s – Recursive-Fallback", doc_id)
        full_text = content.get("full_text", "")
        return _make_recursive_chunks(
            full_text, source_type, doc_id, source_file, "nooutline", {}
        )

    pages_by_num: dict[int, str] = {p["page_number"]: p.get("text", "") for p in pages}
    max_page = max(pages_by_num.keys()) + 1

    # H2-Sektionen mit Seitenbereich bestimmen
    h2_sections: list[dict] = []
    current_h1 = ""
    for i, item in enumerate(outline):
        if item["level"] == 1:
            current_h1 = item["title"]
        elif item["level"] == 2:
            end = max_page
            for j in range(i + 1, len(outline)):
                if outline[j]["level"] <= 2:
                    end = outline[j]["page"]
                    break
            h2_sections.append(
                {
                    "h1": current_h1,
                    "title": item["title"],
                    "start": item["page"],
                    "end": end,
                }
            )

    if not h2_sections:
        logger.warning("Keine H2-Sektionen in %s – Recursive-Fallback", doc_id)
        full_text = content.get("full_text", "")
        return _make_recursive_chunks(
            full_text, source_type, doc_id, source_file, "nooutline", {}
        )

    chunks: list[dict] = []
    section_idx = 0

    for h2 in h2_sections:
        text = _extract_pages_text(pages_by_num, h2["start"], h2["end"])
        if not text:
            continue

        if _token_count(text) <= V1_TOKEN_LIMIT:
            chunks.append(
                {
                    "id": f"{source_type}__{doc_id}_h2_{section_idx:04d}",
                    "text": text,
                    "metadata": {
                        "source_type": source_type,
                        "source_file": source_file,
                        "chunk_index": section_idx,
                        "chunking_strategy": "outline",
                        "outline_path": [h2["h1"], h2["title"]],
                    },
                }
            )
            section_idx += 1
        else:
            # H3-Fallback für diesen H2-Bereich
            h3_secs = _get_h3_sections(outline, h2["start"], h2["end"])

            if not h3_secs:
                # Kein H3 vorhanden → direkt Recursive
                recursive = _make_recursive_chunks(
                    text, source_type, doc_id, source_file,
                    f"h2_{section_idx:04d}",
                    {"outline_path": [h2["h1"], h2["title"]]},
                    start_idx=section_idx,
                )
                chunks.extend(recursive)
                section_idx += len(recursive)
            else:
                for h3 in h3_secs:
                    h3_text = _extract_pages_text(pages_by_num, h3["start"], h3["end"])
                    if not h3_text:
                        continue
                    h3_id = f"{source_type}__{doc_id}_h3_{section_idx:04d}"
                    outline_path = [h2["h1"], h2["title"], h3["title"]]

                    if _token_count(h3_text) <= V1_TOKEN_LIMIT:
                        chunks.append(
                            {
                                "id": h3_id,
                                "text": h3_text,
                                "metadata": {
                                    "source_type": source_type,
                                    "source_file": source_file,
                                    "chunk_index": section_idx,
                                    "chunking_strategy": "outline",
                                    "outline_path": outline_path,
                                },
                            }
                        )
                        section_idx += 1
                    else:
                        recursive = _make_recursive_chunks(
                            h3_text, source_type, doc_id, source_file,
                            f"h3_{section_idx:04d}",
                            {"outline_path": outline_path},
                            start_idx=section_idx,
                        )
                        chunks.extend(recursive)
                        section_idx += len(recursive)

    return chunks


# ── Hauptfunktion ────────────────────────────────────────────────────────────


def chunk_documents_v1(gold_entries: list[dict]) -> list[dict]:
    """V1-Chunking: dispatchet pro Quelltyp auf die passende Strategie.

    Args:
        gold_entries: Liste von Gold-Eintrag-Dicts (eingelesen aus JSONL).

    Returns:
        Liste von Chunk-Dicts mit den Schlüsseln 'id', 'text', 'metadata'.
        Schnittstelle identisch zu V0 (chunk_documents).
    """
    logger.info("V1-Chunking gestartet: %d Gold-Einträge", len(gold_entries))

    chunks: list[dict] = []
    stats: dict[str, int] = {
        "atomic": 0, "outline": 0, "page": 0, "recursive_fallback": 0
    }

    for entry in gold_entries:
        source_type = entry["source_type"]

        if source_type in ("forum", "ticket"):
            entry_chunks = _chunk_atomic(entry, source_type)
        elif source_type in ("modulbeschreibung", "schulungsunterlage"):
            entry_chunks = _chunk_pages(entry, source_type)
        elif source_type == "handbuch":
            entry_chunks = _chunk_outline(entry, source_type)
        else:
            logger.warning(
                "Unbekannter source_type '%s' in %s – verwende V0-Recursive",
                source_type,
                entry.get("doc_id", "?"),
            )
            from rag.index.chunking import chunk_documents  # noqa: PLC0415

            entry_chunks = chunk_documents([entry])

        chunks.extend(entry_chunks)
        for chunk in entry_chunks:
            strat = chunk["metadata"].get("chunking_strategy", "unknown")
            stats[strat] = stats.get(strat, 0) + 1

    logger.info(
        "V1-Chunking abgeschlossen: %d Chunks "
        "(atomic=%d, outline=%d, page=%d, recursive_fallback=%d)",
        len(chunks),
        stats["atomic"],
        stats["outline"],
        stats["page"],
        stats["recursive_fallback"],
    )

    return chunks
