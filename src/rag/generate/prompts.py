"""Prompts: Baut die Chat-Messages für die LLM-Generation zusammen."""

import logging

logger = logging.getLogger(__name__)

_SYSTEM_MESSAGE = (
    "Du bist ein Support-Assistent für SelectLine-ERP-Software. Beantworte die "
    "Frage des Nutzers ausschliesslich auf Basis der bereitgestellten Kontext-"
    "Dokumente. Wenn die Antwort nicht aus dem Kontext hervorgeht, sage das ehrlich "
    "und versuche keine eigene Antwort zu erfinden.\n\n"
    "Gib am Ende deiner Antwort die Quellen an, aus denen die Information stammt. "
    "Format: [Quelle: <source_file>, Chunk <chunk_index>]. Mehrere Quellen werden "
    "mit Komma getrennt aufgelistet."
)


def build_messages(query: str, chunks: list[dict]) -> list[dict]:
    """Baut die OpenAI-Chat-Messages für die Generation.

    Args:
        query: Anfrage des Nutzers.
        chunks: Liste der abgerufenen Chunks (aus retrieve_chunks),
                mit 'text' und 'metadata' (source_file, chunk_index).

    Returns:
        Liste von Message-Dicts mit 'role' und 'content', bereit für
        die OpenAI Chat-API.
    """
    logger.info("Baue Prompt mit %d Kontext-Chunks", len(chunks))

    chunk_blocks: list[str] = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        source_file = meta.get("source_file", "unknown")
        chunk_index = meta.get("chunk_index", 0)
        header = f"[source_file: {source_file}, chunk_index: {chunk_index}]"
        chunk_blocks.append(f"{header}\n{chunk['text']}")

    context = "\n\n".join(chunk_blocks)
    user_content = f"Kontext:\n\n{context}\n\nFrage: {query}"

    return [
        {"role": "system", "content": _SYSTEM_MESSAGE},
        {"role": "user", "content": user_content},
    ]
