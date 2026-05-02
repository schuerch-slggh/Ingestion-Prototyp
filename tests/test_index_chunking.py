"""Tests für die V0-Chunking-Logik (AP-3)."""

import sys
from pathlib import Path

import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.config import CHUNK_SIZE
from rag.index.chunking import chunk_documents

_ENC = tiktoken.get_encoding("cl100k_base")


def _make_entry(
    doc_id: str = "test_doc",
    source_type: str = "forum",
    filename: str = "test.csv",
    full_text: str = "Normaler Testinhalt.",
    extra_content: dict | None = None,
) -> dict:
    """Erstellt einen minimalen Gold-Eintrag."""
    content = {"full_text": full_text}
    if extra_content:
        content.update(extra_content)
    return {
        "doc_id": doc_id,
        "source_type": source_type,
        "metadata": {"filename": filename},
        "content": content,
    }


def _token_count(text: str) -> int:
    return len(_ENC.encode(text))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_chunk_documents_produces_minimal_metadata() -> None:
    """Jeder Chunk darf genau source_type, source_file, chunk_index enthalten."""
    entry = _make_entry(full_text="Ein kurzer Testtext für die Metadaten-Prüfung.")
    chunks = chunk_documents([entry])

    assert len(chunks) >= 1
    for chunk in chunks:
        assert set(chunk["metadata"].keys()) == {"source_type", "source_file", "chunk_index"}, (
            f"Unerwartete Metadaten-Schlüssel: {set(chunk['metadata'].keys())}"
        )
        assert chunk["metadata"]["source_type"] == "forum"
        assert chunk["metadata"]["source_file"] == "test.csv"
        assert isinstance(chunk["metadata"]["chunk_index"], int)


def test_chunk_documents_respects_chunk_size() -> None:
    """Alle Chunks müssen <= CHUNK_SIZE Tokens lang sein."""
    # Erzeuge langen Text (~5000 Tokens): 100 Zeichen × 50 = 5000 Zeichen ≈ 1000+ Tokens
    long_text = ("SelectLine ERP Software Handbuch Kapitel Eins. " * 200).strip()
    assert _token_count(long_text) > CHUNK_SIZE, "Voraussetzung: Text muss länger als CHUNK_SIZE sein"

    entry = _make_entry(full_text=long_text)
    chunks = chunk_documents([entry])

    assert len(chunks) > 1, "Langer Text muss in mehrere Chunks zerlegt werden"
    for chunk in chunks:
        n_tokens = _token_count(chunk["text"])
        assert n_tokens <= CHUNK_SIZE, (
            f"Chunk mit {n_tokens} Tokens überschreitet CHUNK_SIZE={CHUNK_SIZE}"
        )


def test_chunk_documents_handles_short_text() -> None:
    """Kurzer Text (unter CHUNK_SIZE) erzeugt genau einen Chunk."""
    short_text = "Das ist ein kurzer Text."
    assert _token_count(short_text) < CHUNK_SIZE

    entry = _make_entry(full_text=short_text)
    chunks = chunk_documents([entry])

    assert len(chunks) == 1, f"Kurzer Text muss genau 1 Chunk ergeben, war {len(chunks)}"
    assert chunks[0]["metadata"]["chunk_index"] == 0
    assert chunks[0]["id"] == "forum__test_doc_chunk_0000"


def test_chunk_documents_ignores_outline_and_pages() -> None:
    """V0 nutzt nur content.full_text – outline und pages werden ignoriert."""
    entry = _make_entry(
        full_text="Relevanter Volltext für V0.",
        extra_content={
            "outline": [{"level": 1, "title": "Kapitel 1", "page": 1}],
            "pages": [{"page_number": 1, "text": "Seitentext der ignoriert werden soll"}],
        },
    )
    chunks = chunk_documents([entry])

    assert len(chunks) == 1
    assert chunks[0]["text"] == "Relevanter Volltext für V0."
    assert "outline" not in chunks[0]
    assert "pages" not in chunks[0]
    assert set(chunks[0]["metadata"].keys()) == {"source_type", "source_file", "chunk_index"}
