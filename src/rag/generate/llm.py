"""LLM: Wrapper für OpenAI Chat Completions."""

import logging
import time

from openai import OpenAI

from rag.config import LLM_TEMPERATURE, OPENAI_API_KEY, RANDOM_SEED

logger = logging.getLogger(__name__)


def call_llm(messages: list[dict], model: str) -> tuple[str, dict]:
    """Sendet messages an das LLM und gibt die Antwort plus Statistiken zurück.

    Args:
        messages: Liste von Message-Dicts (role/content).
        model: Modell-ID (z. B. "gpt-4.1").

    Returns:
        (answer_text, stats_dict mit Schlüsseln 'input_tokens',
         'output_tokens', 'duration_seconds')
    """
    logger.info("LLM-Aufruf: Modell=%s, %d Messages", model, len(messages))
    client = OpenAI(api_key=OPENAI_API_KEY)

    t0 = time.monotonic()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=LLM_TEMPERATURE,
        seed=RANDOM_SEED,
    )
    duration = time.monotonic() - t0

    answer = response.choices[0].message.content or ""
    stats = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "duration_seconds": round(duration, 3),
    }
    logger.info(
        "LLM-Antwort: %d Zeichen, %d in / %d out Tokens, %.1f s",
        len(answer),
        stats["input_tokens"],
        stats["output_tokens"],
        stats["duration_seconds"],
    )
    return answer, stats
