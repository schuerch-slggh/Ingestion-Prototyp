"""Prompts: Baut den Prompt für das LLM zusammen.

Verantwortung:
- System-Prompt definieren
- Kontext-Chunks und Benutzerfrage in einen Prompt zusammenführen
"""

import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Du bist ein hilfreicher Assistent. Beantworte die Frage ausschliesslich "
    "auf Basis des bereitgestellten Kontexts. Wenn der Kontext die Frage nicht "
    "beantwortet, sage dies ehrlich."
)


def build_prompt(query: str, context_chunks: list[str]) -> list[dict]:
    """Baut die Message-Liste für den LLM-Aufruf zusammen.

    Gibt eine Liste von Message-Dicts (role/content) zurück.
    """
    logger.info("Baue Prompt mit %d Kontext-Chunks", len(context_chunks))

    context = "\n\n---\n\n".join(context_chunks)

    user_content = (
        f"Kontext:\n{context}\n\n"
        f"Frage: {query}\n\n"
        "Antwort:"
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
