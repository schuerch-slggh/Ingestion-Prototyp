"""Vectorstore: Verwaltet den Vektorindex (ChromaDB).

Verantwortung:
- Chunks und Embeddings in eine ChromaDB-Collection einfügen
- Index persistieren (data/index/)
- Bestehenden Index laden
"""

import logging
from pathlib import Path

import chromadb

logger = logging.getLogger(__name__)

COLLECTION_NAME = "naive_rag"


def create_index(
    chunks: list[dict],
    embeddings: list[list[float]],
    persist_dir: Path,
) -> None:
    """Erstellt einen neuen Vektorindex und speichert ihn in *persist_dir*."""
    logger.info("Erstelle Index mit %d Chunks in %s", len(chunks), persist_dir)

    client = chromadb.PersistentClient(path=str(persist_dir))

    # Bestehende Collection entfernen für sauberen Neuaufbau
    try:
        client.delete_collection(COLLECTION_NAME)
    except ValueError:
        pass

    collection = client.create_collection(name=COLLECTION_NAME)

    ids = [c["metadata"]["chunk_id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    batch_size = 500
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            embeddings=embeddings[i:end],
            metadatas=metadatas[i:end],
        )

    logger.info(
        "Index mit %d Einträgen erstellt und persistiert", len(ids)
    )


def load_index(persist_dir: Path) -> chromadb.Collection:
    """Lädt einen bestehenden Vektorindex aus *persist_dir*."""
    logger.info("Lade Index aus %s", persist_dir)
    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_collection(name=COLLECTION_NAME)
    logger.info(
        "Collection '%s' geladen (%d Einträge)",
        COLLECTION_NAME,
        collection.count(),
    )
    return collection
