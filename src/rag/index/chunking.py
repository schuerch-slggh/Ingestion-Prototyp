"""Chunking: Teilt normalisierte Dokumente in kleinere Abschnitte.

Verantwortung:
- Dokumente in Chunks fester Grösse aufteilen
- Overlap zwischen Chunks sicherstellen
- Chunk-Metadaten beibehalten (Quelldokument, Position)
"""

import logging

logger = logging.getLogger(__name__)


def chunk_documents(
    documents: list[dict],
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    """Teilt *documents* in Chunks der Grösse *chunk_size* mit *chunk_overlap*.

    Einfaches zeichenbasiertes Splitting mit Overlap.
    """
    logger.info(
        "Chunking: %d Dokumente, size=%d, overlap=%d",
        len(documents),
        chunk_size,
        chunk_overlap,
    )
    chunks: list[dict] = []
    chunk_counter = 0
    step = chunk_size - chunk_overlap

    for doc in documents:
        text = doc["text"]
        meta = doc.get("metadata", {})
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]

            if chunk_text.strip():
                chunk_counter += 1
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        **meta,
                        "chunk_id": f"chunk_{chunk_counter:05d}",
                        "char_start": start,
                        "char_end": min(end, len(text)),
                    },
                })

            start += step

    logger.info("%d Chunks erstellt", len(chunks))
    return chunks
