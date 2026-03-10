"""Normalize: Bereinigt und vereinheitlicht extrahierten Rohtext.

Verantwortung:
- Whitespace normalisieren
- Sonderzeichen bereinigen
- Einheitliches Dokumentformat sicherstellen
- Ergebnis als normalisierte Dokumente in data/processed/ schreiben
"""

import logging
import re

logger = logging.getLogger(__name__)


def normalize_documents(documents: list[dict]) -> list[dict]:
    """Normalisiert eine Liste von Roh-Dokumenten.

    Bereinigt Whitespace, entfernt Null-Bytes und trimmt Zeilen.
    """
    logger.info("Normalisiere %d Dokumente", len(documents))
    normalized: list[dict] = []

    for doc in documents:
        text = doc["text"]
        text = text.replace("\x00", "")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = "\n".join(line.strip() for line in text.splitlines())
        text = text.strip()

        if not text:
            continue

        normalized.append({
            "text": text,
            "metadata": doc.get("metadata", {}),
        })

    logger.info("%d Dokumente nach Normalisierung übrig", len(normalized))
    return normalized
