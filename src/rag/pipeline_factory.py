"""Pipeline-Factory: Wählt Komponenten je nach Pipeline-Variante.

WICHTIG: Diese Factory wird in AP-3 (V0 End-to-End) neu konzipiert.
Die alte Implementation, die auf src/rag/ingest verwies, wurde mit
AP-2.5 entfernt, da die Datenaufbereitung jetzt in src/rag/preparation
liegt.
"""

from typing import Callable


def get_loaders(variant: str) -> dict[str, Callable]:
    """Liefert Loader-Funktionen für die angegebene Variante.

    Wird in AP-3 mit Bezug auf src/rag/preparation neu implementiert.
    """
    if variant in ("v0", "v1", "v2", "v3"):
        raise NotImplementedError(
            f"Loader für Variante '{variant}' werden in AP-3 neu implementiert. "
            "Datenaufbereitung erfolgt aktuell über die quellenspezifischen "
            "scripts/Pipeline/00_prepare_*.py-Skripte."
        )
    raise ValueError(f"Unbekannte Variante: '{variant}'")


def get_chunker(variant: str) -> Callable:
    """Liefert die Chunking-Funktion für die angegebene Variante.

    Wird in AP-3 implementiert.
    """
    if variant in ("v0", "v1", "v2", "v3"):
        raise NotImplementedError(
            f"Chunker für Variante '{variant}' werden in AP-3 implementiert."
        )
    raise ValueError(f"Unbekannte Variante: '{variant}'")
