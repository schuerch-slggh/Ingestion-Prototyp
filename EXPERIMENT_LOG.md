# Experiment Log

Pro Eintrag: Datum, Variante, Änderung, beobachteter Effekt.

---

## 2026-05-02 – AP-2.5: Repo-Aufräumen nach Datenaufbereitungs-APs

Aufräumarbeiten nach Abschluss der Datenaufbereitungs-APs (AP-2a bis AP-2e):

- Duplikat `.github/CLAUDE.md` entfernt (Claude-Konfig nur noch im Root)
- `src/rag/ingest/` war bereits nicht mehr vorhanden (wurde offenbar schon entfernt)
- `scripts/Pipeline/01_ingest.py` gelöscht (ersetzt durch `00_prepare_*.py`)
- `src/rag/pipeline_factory.py` mit `NotImplementedError`-Stubs versehen;
  Neuimplementation in AP-3 (alte Imports auf `rag.ingest` entfernt)
- `scripts/transformation/forum_encoding_fix.py` gelöscht
  (Logik liegt vollständig in `preparation/forum.py`)
- `.gitignore` modernisiert: spezifische `data/raw|interim|processed|index|eval`-
  Einträge entfernt (redundant zu pauschaler `data/`-Regel); `runs/naive_rag`-
  Eintrag entfernt
- `runs/naive_rag/` entfernt; `NAIVE_RAG_RUNS_DIR` aus `config.py` entfernt
- Alle fünf `00_prepare_*.py`-Skripte weiterhin lauffähig (Smoke-Tests bestanden)
- 23/23 Tests bestanden

---

## 2026-05-02 – AP-2e: Schulungsunterlagen + pages-Array in Gold-Schema (PDF)

- Modul `src/rag/preparation/schulungsunterlagen.py` (analog zu handbuecher.py,
  flaches glob, source_type="schulungsunterlage", kein Outline erwartet)
- Pipeline-Skript `scripts/Pipeline/00_prepare_schulungsunterlagen.py`
- Gold-Schema für alle PDF-Quellen erweitert: `content.pages` als Array von
  `{page_number, text}`-Dicts (Grundlage für V1-Chunking per Seite)
- `clean_to_silver()` in allen drei PDF-Modulen: Boilerplate-Bereinigung jetzt
  pro Seite; `full_text` wird aus bereinigten Seiten zusammengesetzt (Konsistenz)
- `transform_to_gold()` in allen drei PDF-Modulen: `pages_json` → `content.pages`
- Pipeline-Skripte (handbuecher, modulbeschreibungen, schulungsunterlagen):
  `pages_json` wird beim CSV-Export gedroppt (nicht CSV-kompatibel)
- Schulungsunterlagen: 19 PDFs, 937 Seiten, 1'319 Bilder (alle ohne Outline)
- Handbücher neu generiert: 8 PDFs, 9'082 Seiten, 6'253 Bilder
- Modulbeschreibungen neu generiert: 63 PDFs, 1'053 Seiten, 1'542 Bilder
- Tests: 23/23 bestanden (6 neue Tests: 3 schulungsunterlagen + 1 handbuecher +
  1 modulbeschreibungen + Fixture-Fix für pages-losen _make_doc)

---

## 2026-05-01 – AP-2d: Modulbeschreibungen-Datenaufbereitung

- Modul `src/rag/preparation/modulbeschreibungen.py` (analog zu handbuecher.py,
  rglob für Unterordner, source_type="modulbeschreibung")
- Pipeline-Skript `scripts/Pipeline/00_prepare_modulbeschreibungen.py`
- Boilerplate-Pattern `BOILERPLATE_PATTERNS` + `remove_boilerplate()` nach
  `pdf_reader.py` extrahiert (gemeinsam genutzt von handbuecher.py und
  modulbeschreibungen.py); neues Pattern: `^Seite\s+\d+` (für "Seite X von Y")
- 63 PDFs in 12 Unterordnern, 1'053 Seiten, 1'542 Bilder extrahiert
- Outline-Statistik: 3/63 Dokumente mit Outline, 60 ohne → robust behandelt
- Tests 3/3 bestanden; alle bisherigen Tests weiterhin grün (7/7)

---

## 2026-05-01 – AP-2c: Handbuch-Datenaufbereitung

- Modul `src/rag/preparation/pdf_reader.py` (PyMuPDF-basiert, generisch
  wiederverwendbar für alle PDF-Quellen: Text, Outline, Bild-Extraktion)
- Modul `src/rag/preparation/handbuecher.py` (load_bronze, clean_to_silver, transform_to_gold)
- Pipeline-Skript `scripts/Pipeline/00_prepare_handbuecher.py`
- Bilder als PNG nach data/gold/images/<doc_id>/ extrahiert; Bilder <50×50px verworfen
- Outline als strukturierte Liste in Gold-Schicht (für V1-Chunking)
- Boilerplate-Filter (isolierte Seitenzahlen, Copyright-Zeilen)
- Dependency: pymupdf>=1.24 (installiert: 1.27.2)
- 8 PDFs, 9'082 Seiten, 6'253 Bilder extrahiert (2'782 gefiltert als zu klein)
  (inkl. SelectLine System Handbuch: 1'512 Seiten, 1'084 Outline-Einträge)
- Tests 4/4 bestanden

---

## 2026-05-01 – AP-2b: Ticket-Datenaufbereitung

- Modul `src/rag/preparation/dbf_reader.py` (DBF-Lese-Logik aus
  `scripts/transformation/ticket_dbf_to_csv.py` extrahiert,
  Pfad-Hartcodierung entfernt, API gibt DataFrame statt CSV zurück)
- Modul `src/rag/preparation/tickets.py` (load_bronze, clean_to_silver, transform_to_gold)
- Lookup-Tabellen `PRODUCT_LOOKUP` und `TICKET_STATUS_LOOKUP` in `lookups.py`
- Pipeline-Skript `scripts/Pipeline/00_prepare_tickets.py`
- Filter: nur Tickets mit nicht-leerem LOESUNG-Feld (18'609 → 4'691)
- Gold-Format mit strukturierten Markern (Fehlerbeschreibung:, Lösung:)
- Tests für DBF-Lese-Logik und alle drei Verarbeitungsstufen (5/5 bestanden)
- Altes Skript `ticket_dbf_to_csv.py` als Wrapper reduziert
- 645 E-Mail-Signaturen entfernt, 468 HTML-Felder bereinigt

---

## 2026-05-01 – AP-2a.1: Pfadstruktur korrigieren

- `PROCESSED_DIR` umbenannt zu `GOLD_DIR` (Datenaufbereitung, variantenunabhängig)
- Neuer Pfad `CHUNKS_DIR` für variantenspezifische Chunks (Ingestion)
- `get_variant_processed_dir()` entfernt, ersetzt durch `get_variant_chunks_dir()`
- Verwendungsstellen in `00_prepare_forum.py` und `02_index.py` angepasst
- Klare Trennung zwischen Datenaufbereitung (Kap. 5) und Ingestion (Kap. 6)

---

## 2026-05-01 – AP-2a: Forum-Datenaufbereitung

- Submodul `src/rag/preparation/` mit Modulen `lookups.py`, `jsonl_writer.py`, `forum.py`
- Pipeline-Skript `scripts/Pipeline/00_prepare_forum.py`
- Bronze→Silver→Gold-Verarbeitung für Forum-Quelle
- Encoding-Korrektur (Latin-1/UTF-8 Mojibake-Fix), Spaltenfilterung, BBCode/HTML-Entfernung,
  Modul-Code-Auflösung, Deduplizierung, JSONL-Export
- 2058 Bronze-Beiträge → 2052 Silver/Gold (6 Duplikate entfernt)
- Tests für alle drei Verarbeitungsstufen (6/6 bestanden)
- Quelldatei: `data/bronze/forum/forum.csv` (Trennzeichen: `;`, 26 phpBB-Spalten)

---

## 2026-04-30 – AP-1.5: Konfigurations-Synchronisation

- EMBEDDING_MODEL Default auf `text-embedding-3-large` (DE-1)
- LLM_MODEL Default auf `gpt-4.1` (DE-3)
- CHUNK_SIZE 800, CHUNK_OVERLAP 100 (DE-4)
- LLM_TEMPERATURE als neue Konfiguration mit Default 0.0 (DE-7)
- `.env.example` entsprechend aktualisiert
- V0 weiterhin lauffähig

---

## 2026-04-28 – AP-1: Repo-Refactor

- Variant-Switch eingeführt (Default V0)
- Variantenspezifische Pfade für Index, Processed, Eval
- Pipeline-Factory als Entkopplungsschicht
- Skripte nach `scripts/Pipeline/` verschoben
- V0 weiterhin lauffähig
