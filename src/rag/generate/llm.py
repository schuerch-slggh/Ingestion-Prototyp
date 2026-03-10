"""LLM: Wrapper für den LLM-Aufruf.

Verantwortung:
- Prompt an das LLM senden (OpenAI Chat Completion)
- Antwort zurückgeben
"""

import logging

from openai import OpenAI

from rag.config import OPENAI_API_KEY, RANDOM_SEED

logger = logging.getLogger(__name__)


def call_llm(messages: list[dict], model: str) -> str:
    """Sendet *messages* an das LLM und gibt die Antwort als String zurück."""
    logger.info("LLM-Aufruf mit Modell '%s'", model)

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,
        seed=RANDOM_SEED,
    )

    answer = response.choices[0].message.content or ""
    logger.info("LLM-Antwort erhalten (%d Zeichen)", len(answer))
    return answer
