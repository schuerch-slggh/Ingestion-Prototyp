"""Embeddings: Berechnet Vektorrepräsentationen für Text-Chunks."""

import logging

from openai import OpenAI

from rag.config import EMBEDDING_MODEL, OPENAI_API_KEY

logger = logging.getLogger(__name__)


def embed_query(text: str) -> list[float]:
    """Erzeugt das Embedding für einen einzelnen Query-Text.

    Args:
        text: Anfrage-String.

    Returns:
        Embedding-Vektor als Liste von Floats.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
    return response.data[0].embedding


def embed_chunks(chunks: list[dict], batch_size: int = 100) -> list[list[float]]:
    """Erzeugt Embeddings für alle Chunks via OpenAI text-embedding-3-large.

    Args:
        chunks: Liste von Chunk-Dicts mit 'text'-Feld.
        batch_size: Anzahl Texte pro API-Call (OpenAI erlaubt bis 2048).

    Returns:
        Liste von Embedding-Vektoren in derselben Reihenfolge wie chunks.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)
    embeddings: list[list[float]] = []
    total = len(chunks)
    n_batches = (total + batch_size - 1) // batch_size

    logger.info(
        "Embeddings: %d Chunks, %d Batches à %d (Modell: %s)",
        total,
        n_batches,
        batch_size,
        EMBEDDING_MODEL,
    )

    for i in range(0, total, batch_size):
        batch_texts = [c["text"] for c in chunks[i : i + batch_size]]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch_texts)
        embeddings.extend(item.embedding for item in response.data)

        batch_num = i // batch_size + 1
        if batch_num % 5 == 0 or batch_num == n_batches:
            logger.info("  Batch %d/%d verarbeitet (%d Embeddings)", batch_num, n_batches, len(embeddings))

    return embeddings
