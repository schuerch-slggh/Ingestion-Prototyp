"""Retriever: Findet die relevantesten Chunks zu einer Benutzeranfrage.

Verantwortung:
- Query-Embedding berechnen
- Top-K ähnlichste Chunks aus dem Vektorindex abrufen
- Ergebnisse mit Metadaten zurückgeben
"""

import logging

import chromadb

logger = logging.getLogger(__name__)


def retrieve(
    query_embedding: list[float],
    collection: chromadb.Collection,
    top_k: int,
) -> list[dict]:
    """Sucht die *top_k* relevantesten Chunks per Ähnlichkeitssuche.

    Erwartet ein vorberechnetes Query-Embedding.
    Gibt eine Liste von Chunk-Dicts mit ``text``, ``metadata`` und
    ``score`` zurück.
    """
    logger.info("Retrieval: top_k=%d", top_k)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    retrieved: list[dict] = []
    for i in range(len(results["ids"][0])):
        retrieved.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": results["distances"][0][i],
        })

    logger.info("%d Chunks abgerufen", len(retrieved))
    return retrieved
