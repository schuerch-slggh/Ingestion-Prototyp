"""Pipeline-Factory: Wählt Komponenten je nach Pipeline-Variante.

get_loaders ist nicht mehr nötig (Datenaufbereitung erfolgt über
quellenspezifische 00_prepare_*.py-Skripte). get_chunker liefert die
V0-Chunking-Funktion; V1–V3 werden in späteren APs implementiert.
"""

from typing import Callable


def get_loaders(variant: str) -> dict[str, Callable]:
    """Nicht mehr benötigt – Datenaufbereitung erfolgt über 00_prepare_*.py."""
    raise NotImplementedError(
        "get_loaders wird nicht mehr verwendet. Datenaufbereitung erfolgt "
        "über die quellenspezifischen scripts/Pipeline/00_prepare_*.py-Skripte."
    )


def get_chunker(variant: str) -> Callable:
    """Liefert die Chunking-Funktion für die angegebene Variante.

    Args:
        variant: Pipeline-Variante ("v0", "v1", "v2", "v3").

    Returns:
        Callable mit Signatur (gold_entries: list[dict]) -> list[dict].
    """
    if variant == "v0":
        from rag.index.chunking import chunk_documents
        return chunk_documents
    if variant == "v1":
        from rag.index.chunking_v1 import chunk_documents_v1
        return chunk_documents_v1
    if variant == "v2":
        from rag.index.chunking_v2 import chunk_documents_v2
        return chunk_documents_v2
    if variant == "v3":
        # V3 nutzt denselben Chunker und Index wie V2
        from rag.index.chunking_v2 import chunk_documents_v2
        return chunk_documents_v2
    if variant == "v4":
        from rag.index.chunking_v4 import chunk_documents_v4
        return chunk_documents_v4
    raise ValueError(f"Unbekannte Variante: '{variant}'")
