"""Vectorstore: ChromaDB-Wrapper für variantenspezifische Collections."""

import logging

import chromadb

from rag.config import get_variant_index_dir

logger = logging.getLogger(__name__)

COLLECTION_NAME = "v0_index"


def get_or_create_collection(
    variant: str, reset: bool = False
) -> chromadb.Collection:
    """Liefert eine ChromaDB-Collection für die angegebene Variante.

    Args:
        variant: Pipeline-Variante (z. B. "v0").
        reset: Wenn True, wird eine bestehende Collection gelöscht und neu erstellt.

    Returns:
        ChromaDB-Collection-Objekt.
    """
    index_dir = get_variant_index_dir(variant)
    index_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_dir))

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info("Bestehende Collection '%s' gelöscht.", COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    logger.info(
        "Collection '%s' bereit (%d Einträge).", COLLECTION_NAME, collection.count()
    )
    return collection


def add_chunks_to_collection(
    collection: chromadb.Collection,
    chunks: list[dict],
    embeddings: list[list[float]],
    batch_size: int = 500,
) -> None:
    """Fügt Chunks und ihre Embeddings einer Collection hinzu.

    Args:
        collection: Ziel-Collection.
        chunks: Chunk-Dicts mit 'id', 'text', 'metadata'.
        embeddings: Vektoren in derselben Reihenfolge wie chunks.
        batch_size: Einträge pro ChromaDB-Add-Call.
    """
    total = len(chunks)
    logger.info("Füge %d Chunks in Collection ein …", total)

    for i in range(0, total, batch_size):
        end = min(i + batch_size, total)
        collection.add(
            ids=[c["id"] for c in chunks[i:end]],
            documents=[c["text"] for c in chunks[i:end]],
            metadatas=[c["metadata"] for c in chunks[i:end]],
            embeddings=embeddings[i:end],
        )

    logger.info("Collection enthält jetzt %d Einträge.", collection.count())
