"""Chunking: Zerlegt Gold-Einträge in Chunks für die Indexierung.

V0-Ansatz: Quelltypagnostisches tokenbasiertes Splitting mit tiktoken.
Alle Quellen werden gleich behandelt – kein quellenspezifisches Chunking.
"""

import logging

import tiktoken

from rag.config import CHUNK_OVERLAP, CHUNK_SIZE

logger = logging.getLogger(__name__)

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Zerlegt *text* in überlappende Token-Fenster."""
    tokens = _ENCODING.encode(text)
    if not tokens:
        return []

    chunks: list[str] = []
    step = chunk_size - chunk_overlap
    start = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_text = _ENCODING.decode(tokens[start:end])
        if chunk_text.strip():
            chunks.append(chunk_text)
        if end == len(tokens):
            break
        start += step

    return chunks


def chunk_documents(gold_entries: list[dict]) -> list[dict]:
    """V0-Chunking: zerlegt content.full_text aller Gold-Einträge gleichförmig.

    Args:
        gold_entries: Liste von Gold-Eintrag-Dicts (eingelesen aus JSONL).

    Returns:
        Liste von Chunk-Dicts mit den Schlüsseln 'id', 'text', 'metadata'.
        metadata enthält ausschliesslich source_type, source_file, chunk_index.
    """
    logger.info(
        "V0-Chunking: %d Gold-Einträge, size=%d, overlap=%d",
        len(gold_entries),
        CHUNK_SIZE,
        CHUNK_OVERLAP,
    )
    result: list[dict] = []

    for entry in gold_entries:
        doc_id = entry["doc_id"]
        source_type = entry["source_type"]
        source_file = entry.get("metadata", {}).get("filename", "unknown")
        full_text = entry.get("content", {}).get("full_text", "")

        text_chunks = _split_text(full_text, CHUNK_SIZE, CHUNK_OVERLAP)

        for chunk_index, chunk_text in enumerate(text_chunks):
            result.append({
                "id": f"{source_type}__{doc_id}_chunk_{chunk_index:04d}",
                "text": chunk_text,
                "metadata": {
                    "source_type": source_type,
                    "source_file": source_file,
                    "chunk_index": chunk_index,
                },
            })

    logger.info("%d Chunks aus %d Einträgen erstellt", len(result), len(gold_entries))
    return result
