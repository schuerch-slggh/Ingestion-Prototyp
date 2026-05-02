"""Retriever: Findet die relevantesten Chunks zu einer Benutzeranfrage."""

import logging

from rag.config import TOP_K
from rag.index.embeddings import embed_query
from rag.index.vectorstore import get_or_create_collection

logger = logging.getLogger(__name__)


def retrieve_chunks(
    query: str, variant: str, top_k: int | None = None
) -> list[dict]:
    """Ruft die k ähnlichsten Chunks aus dem variantenspezifischen Index ab.

    Args:
        query: Anfrage-Text.
        variant: Pipeline-Variante (z. B. "v0").
        top_k: Anzahl abzurufender Chunks. Falls None, wird TOP_K aus
               config.py verwendet.

    Returns:
        Liste von Chunk-Dicts mit Schlüsseln 'id', 'text', 'metadata',
        'similarity'. Reihenfolge: absteigend nach Ähnlichkeit.
    """
    k = top_k if top_k is not None else TOP_K
    logger.info("Retrieval: query='%s…', variant=%s, top_k=%d", query[:50], variant, k)

    query_embedding = embed_query(query)
    collection = get_or_create_collection(variant)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[dict] = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        chunks.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "similarity": round(1.0 - distance, 6),
        })

    logger.info("%d Chunks abgerufen (top similarity: %.4f)", len(chunks), chunks[0]["similarity"] if chunks else 0)
    return chunks
