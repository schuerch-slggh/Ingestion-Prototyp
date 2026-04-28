"""Pipeline-Factory: Wählt Komponenten je nach Pipeline-Variante.

V0 ist aktuell implementiert. V1, V2 und V3 sind Platzhalter für
nachfolgende Arbeitspakete.
"""

from typing import Callable


def get_loaders(variant: str) -> dict[str, Callable]:
    """Liefert Loader-Funktionen für die angegebene Variante.

    Schlüssel: Quelltyp (z. B. "pdf", "csv"). Wert: Loader-Funktion.
    """
    if variant == "v0":
        from rag.ingest.csv_loader import load_csvs
        from rag.ingest.pdf_loader import load_pdfs

        return {"pdf": load_pdfs, "csv": load_csvs}
    if variant in ("v1", "v2", "v3"):
        raise NotImplementedError(
            f"Loader für Variante '{variant}' werden in einem "
            "späteren Arbeitspaket implementiert."
        )
    raise ValueError(f"Unbekannte Variante: '{variant}'")


def get_chunker(variant: str) -> Callable:
    """Liefert die Chunking-Funktion für die angegebene Variante."""
    if variant == "v0":
        from rag.index.chunking import chunk_documents

        return chunk_documents
    if variant in ("v1", "v2", "v3"):
        raise NotImplementedError(
            f"Chunker für Variante '{variant}' werden in einem "
            "späteren Arbeitspaket implementiert."
        )
    raise ValueError(f"Unbekannte Variante: '{variant}'")
