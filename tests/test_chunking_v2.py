"""Tests für den V2-Chunker und Metadaten-Anreicherung (AP-6.1)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.index.chunking_v2 import (
    _derive_doc_title,
    _derive_module_from_doc_id,
    _enrich_forum,
    _enrich_handbuch,
    _enrich_modulbeschreibung,
    _enrich_schulungsunterlage,
    _enrich_ticket,
    _extract_doc_id,
    _serialize_outline_path,
    chunk_documents_v2,  # noqa: E402
)

# ── Mock: LLM-Tagger in allen V2-Tests deaktivieren ─────────────────────────


@pytest.fixture(autouse=True)
def mock_llm_tagger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mockt den LLM-Tagger für alle V2-Tests (kein API-Call)."""

    def _stub_tag_chunks(
        chunks: list[dict], cache_path: object = None
    ) -> list[dict]:
        for c in chunks:
            c["metadata"]["module_tags"] = ""
            c["metadata"]["thema_tags"] = ""
            c["metadata"]["typ_tags"] = ""
        return chunks

    monkeypatch.setattr("rag.index.chunking_v2.tag_chunks", _stub_tag_chunks)


# ── Hilfsfunktionen für synthetische Gold-Einträge ───────────────────────────


def _make_forum_entry(
    doc_id: str = "forum_001",
    post_id: str = "001",
    topic_id: str = "10",
    module: str = "SelectLine Auftrag",
    post_date: str = "2023-01-01",
    text: str = "Forumbeitrag Text.",
) -> dict:
    return {
        "doc_id": doc_id,
        "source_type": "forum",
        "metadata": {
            "post_id": post_id,
            "topic_id": topic_id,
            "module": module,
            "post_date": post_date,
        },
        "content": {"full_text": text},
    }


def _make_ticket_entry(
    doc_id: str = "ticket_001",
    ticket_id: str = "001",
    product: str = "Auftrag",
    category: str = "Fehler",
    version_reported: str = "25.1",
    version_resolved: str = "25.2",
    processed_date: str = "2024-03-01",
    text: str = "Ticket Beschreibung.",
) -> dict:
    return {
        "doc_id": doc_id,
        "source_type": "ticket",
        "metadata": {
            "ticket_id": ticket_id,
            "product": product,
            "category": category,
            "version_reported": version_reported,
            "version_resolved": version_resolved,
            "processed_date": processed_date,
        },
        "content": {"full_text": text},
    }


def _make_handbuch_entry(
    doc_id: str = "handbuch_001",
    source_file: str = "SelectLine_Auftrag.pdf",
    outline: list[dict] | None = None,
    pages: list[dict] | None = None,
) -> dict:
    if outline is None:
        outline = [
            {"level": 1, "title": "Kapitel 1", "page": 1},
            {"level": 2, "title": "Abschnitt 1.1", "page": 2},
            {"level": 2, "title": "Abschnitt 1.2", "page": 5},
        ]
    if pages is None:
        pages = [{"page_number": i, "text": f"Text Seite {i}"} for i in range(1, 8)]
    return {
        "doc_id": doc_id,
        "source_type": "handbuch",
        "metadata": {"filename": source_file},
        "content": {
            "full_text": " ".join(p["text"] for p in pages),
            "outline": outline,
            "pages": pages,
        },
    }


def _make_modul_entry(
    doc_id: str = "beschreibung_cloudkasse",
    source_file: str = "Beschreibung_Cloudkasse.pdf",
    pages: list[dict] | None = None,
) -> dict:
    if pages is None:
        pages = [{"page_number": 1, "text": "Modultext."}]
    return {
        "doc_id": doc_id,
        "source_type": "modulbeschreibung",
        "metadata": {"filename": source_file},
        "content": {
            "full_text": "Modultext.",
            "outline": [],
            "pages": pages,
        },
    }


def _make_schulung_entry(
    doc_id: str = "schulungsunterlagen_auftrag_profi",
    source_file: str = "Auftrag_Schulung_Profi.pdf",
    pages: list[dict] | None = None,
) -> dict:
    if pages is None:
        pages = [{"page_number": 1, "text": "Schulungstext."}]
    return {
        "doc_id": doc_id,
        "source_type": "schulungsunterlage",
        "metadata": {"filename": source_file},
        "content": {
            "full_text": "Schulungstext.",
            "outline": [],
            "pages": pages,
        },
    }


# ── Hilfsfunktionen (4 Tests) ────────────────────────────────────────────────


def test_derive_doc_title_basic() -> None:
    assert _derive_doc_title("SelectLine_Auftrag_Handbuch.pdf") == (
        "SelectLine Auftrag Handbuch"
    )


def test_derive_doc_title_no_extension() -> None:
    assert _derive_doc_title("Anleitung") == "Anleitung"


def test_derive_module_from_doc_id_basic() -> None:
    assert _derive_module_from_doc_id("schulungsunterlagen_auftrag_einsteiger") == (
        "Auftrag"
    )


def test_derive_module_from_doc_id_too_short() -> None:
    # Token "A" is 1 char — below MIN_MODULE_TOKEN_LENGTH (3)
    assert _derive_module_from_doc_id("schulungsunterlagen_A_rest") == ""


# ── Anreicherung pro Quelltyp (5 Tests) ─────────────────────────────────────


def test_enrich_forum_adds_metadata() -> None:
    entry = _make_forum_entry(post_id="118", topic_id="100", module="SL Auftrag")
    meta: dict = {"source_type": "forum", "source_file": "forum.jsonl"}
    _enrich_forum(meta, entry)
    assert meta["post_id"] == "118"
    assert meta["topic_id"] == "100"
    assert meta["module_lookup"] == "SL Auftrag"
    assert meta["post_date"] == "2023-01-01"


def test_enrich_ticket_adds_metadata() -> None:
    entry = _make_ticket_entry(ticket_id="76", product="Auftrag", category="1000")
    meta: dict = {"source_type": "ticket", "source_file": "tickets.jsonl"}
    _enrich_ticket(meta, entry)
    assert meta["ticket_id"] == "76"
    assert meta["product"] == "Auftrag"
    assert meta["category"] == "1000"
    assert meta["version_reported"] == "25.1"
    assert meta["version_resolved"] == "25.2"
    assert meta["processed_date"] == "2024-03-01"


def test_enrich_handbuch_adds_metadata() -> None:
    entry = _make_handbuch_entry(source_file="SelectLine_Auftrag.pdf")
    meta: dict = {
        "source_type": "handbuch",
        "source_file": "SelectLine_Auftrag.pdf",
        "outline_path": ["Kapitel 1", "Abschnitt 1.1"],
    }
    _enrich_handbuch(meta, entry)
    assert meta["doc_title"] == "SelectLine Auftrag"
    assert meta["outline_level"] == 2
    assert meta["page_start"] == 2
    assert meta["page_end"] == 5
    # outline_path serialised to string
    assert isinstance(meta["outline_path"], str)
    assert "Kapitel 1" in meta["outline_path"]
    assert " > " in meta["outline_path"]


def test_enrich_modulbeschreibung_adds_metadata() -> None:
    entry = _make_modul_entry(source_file="Beschreibung_Cloudkasse.pdf")
    meta: dict = {
        "source_type": "modulbeschreibung",
        "source_file": "Beschreibung_Cloudkasse.pdf",
        "page_number": 1,
    }
    _enrich_modulbeschreibung(meta, entry)
    assert meta["doc_title"] == "Beschreibung Cloudkasse"


def test_enrich_schulungsunterlage_derives_module() -> None:
    entry = _make_schulung_entry(doc_id="schulungsunterlagen_auftrag_profi")
    meta: dict = {
        "source_type": "schulungsunterlage",
        "source_file": "Auftrag_Schulung_Profi.pdf",
        "page_number": 1,
    }
    _enrich_schulungsunterlage(meta, entry)
    assert meta["module_filename"] == "Auftrag"
    assert meta["doc_title"] == "Auftrag Schulung Profi"


# ── Edge Cases (3 Tests) ─────────────────────────────────────────────────────


def test_enrich_forum_missing_field_yields_empty_string() -> None:
    entry = {
        "doc_id": "forum_999",
        "source_type": "forum",
        "metadata": {},  # no post_date
        "content": {"full_text": "Text."},
    }
    meta: dict = {}
    _enrich_forum(meta, entry)
    assert meta["post_date"] == ""
    assert meta["post_id"] == ""


def test_outline_path_serialized_as_string() -> None:
    path = ["Kapitel 1", "Abschnitt 1.1", "Unterabschnitt 1.1.1"]
    result = _serialize_outline_path(path)
    assert result == "Kapitel 1 > Abschnitt 1.1 > Unterabschnitt 1.1.1"


def test_enrich_handles_recursive_fallback_chunks() -> None:
    """Recursive-Fallback-Chunks erben outline_path und bekommen outline_level."""
    entry = _make_handbuch_entry(source_file="SL_Handbuch.pdf")
    meta: dict = {
        "source_type": "handbuch",
        "source_file": "SL_Handbuch.pdf",
        "chunking_strategy": "recursive_fallback",
        "outline_path": ["Kapitel 1", "Abschnitt 1.1"],  # inherited from H2
    }
    _enrich_handbuch(meta, entry)
    assert meta["outline_level"] == 2
    assert isinstance(meta["outline_path"], str)
    assert meta["doc_title"] == "SL Handbuch"


# ── _extract_doc_id (6 Tests) ────────────────────────────────────────────────


def test_extract_doc_id_atomic() -> None:
    assert _extract_doc_id("forum__forum_001", "forum") == "forum_001"


def test_extract_doc_id_page() -> None:
    assert (
        _extract_doc_id(
            "modulbeschreibung__beschreibung_cloudkasse_page_0001",
            "modulbeschreibung",
        )
        == "beschreibung_cloudkasse"
    )


def test_extract_doc_id_h2() -> None:
    assert _extract_doc_id("handbuch__doc_id_h2_0001", "handbuch") == "doc_id"


def test_extract_doc_id_overflow_recursive() -> None:
    assert (
        _extract_doc_id("forum__forum_001_overflow_recursive_0000", "forum")
        == "forum_001"
    )


def test_extract_doc_id_h2_recursive() -> None:
    assert (
        _extract_doc_id("handbuch__doc_id_h2_0001_recursive_0000", "handbuch")
        == "doc_id"
    )


def test_extract_doc_id_nooutline_recursive() -> None:
    assert (
        _extract_doc_id(
            "handbuch__doc_id_nooutline_recursive_0000", "handbuch"
        )
        == "doc_id"
    )


# ── Dispatch und Integration (2 Tests) ───────────────────────────────────────


def test_chunk_documents_v2_dispatches_correctly() -> None:
    """Mix aus 5 Einträgen → alle Chunks haben quelltyp-spezifische Felder."""
    entries = [
        _make_forum_entry(),
        _make_ticket_entry(),
        _make_handbuch_entry(),
        _make_modul_entry(),
        _make_schulung_entry(),
    ]
    chunks = chunk_documents_v2(entries)
    assert len(chunks) > 0

    by_type: dict[str, list[dict]] = {}
    for c in chunks:
        st = c["metadata"]["source_type"]
        by_type.setdefault(st, []).append(c)

    # Forum
    assert "post_id" in by_type["forum"][0]["metadata"]
    assert "topic_id" in by_type["forum"][0]["metadata"]
    # Ticket
    assert "ticket_id" in by_type["ticket"][0]["metadata"]
    assert "version_resolved" in by_type["ticket"][0]["metadata"]
    # Handbuch
    assert "outline_level" in by_type["handbuch"][0]["metadata"]
    assert "doc_title" in by_type["handbuch"][0]["metadata"]
    # Modulbeschreibung
    assert "doc_title" in by_type["modulbeschreibung"][0]["metadata"]
    # Schulungsunterlage
    assert "module_filename" in by_type["schulungsunterlage"][0]["metadata"]
    assert "doc_title" in by_type["schulungsunterlage"][0]["metadata"]


def test_v2_metadata_compatible_with_chromadb_types() -> None:
    """Alle V2-Metadaten-Werte sind str/int/float/bool — keine None, keine Listen."""
    entries = [
        _make_forum_entry(),
        _make_ticket_entry(),
        _make_handbuch_entry(),
        _make_modul_entry(),
        _make_schulung_entry(),
    ]
    chunks = chunk_documents_v2(entries)

    violations = []
    for chunk in chunks:
        for k, v in chunk["metadata"].items():
            if v is None:
                violations.append(f"{chunk['id']}: {k} is None")
            if isinstance(v, list):
                violations.append(f"{chunk['id']}: {k} is list ({v!r})")
            if not isinstance(v, (str, int, float, bool)):
                violations.append(f"{chunk['id']}: {k} has type {type(v)}")

    assert violations == [], "\n".join(violations[:5])
