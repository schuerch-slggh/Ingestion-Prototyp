"""Embeddings: Berechnet Vektorrepräsentationen für Text-Chunks.

Verantwortung:
- Chunks an ein Embedding-Modell senden
- Vektoren zurückgeben
"""

import logging

from openai import OpenAI

from rag.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


def embed_texts(texts: list[str], model: str) -> list[list[float]]:
    """Berechnet Embeddings für eine Liste von Texten mit dem angegebenen *model*.

    Sendet Texte in Batches an die OpenAI Embeddings API.
    """
    logger.info(
        "Berechne Embeddings für %d Texte mit Modell '%s'",
        len(texts),
        model,
    )
    client = OpenAI(api_key=OPENAI_API_KEY)
    embeddings: list[list[float]] = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(input=batch, model=model)
        embeddings.extend([item.embedding for item in response.data])
        logger.info("Batch %d–%d verarbeitet", i + 1, i + len(batch))

    return embeddings
