# Experiment Log

Pro Eintrag: Datum, Variante, Änderung, beobachteter Effekt.

---

## 2026-05-08 – AP-4.3: RAGAS-Scorer und Reporter

- `src/rag/evaluate/scorer.py`: RAGAS-Bewertung auf Response-Bundle
  - Drei Metriken: Faithfulness, ResponseRelevancy,
    LLMContextPrecisionWithoutReference (RAGAS 0.2.15)
  - Judge-LLM: gpt-4o (Begründung in Kap. 7 der Arbeit)
  - Filtert Bundle-Einträge mit `error != null` heraus
  - Persistiert Pro-Frage-Scores als JSON mit Metadaten
- `src/rag/evaluate/reporter.py`: Aggregation und Markdown-Output
  - `build_summary()`: Gesamt- und Kategorie-Mittelwerte
  - `write_markdown()`: Tabellen-Format für Kap. 8 der Arbeit
  - None-Scores werden ausgeschlossen (nicht als 0 gewertet)
- `scripts/Pipeline/04_evaluate.py`: `--score`, `--bundle`, `--no-runner`
  - Bugfix: `--bundle` impliziert nun `--no-runner` (verhindert
    versehentlichen Vollauf beim Scoren eines bestehenden Bundles)
- `src/rag/config.py`: `RAGAS_JUDGE_MODEL`, `_TEMPERATURE`, `_SEED`
- `pyproject.toml`: `ragas>=0.2.0,<0.3`, `langchain-openai>=0.3`, `tqdm>=4.0`
- `tests/test_scorer.py`: 6 Tests mit RAGAS-Mocks (kein API-Call)
- `tests/test_reporter.py`: 5 Tests, pure (kein RAGAS, keine API)
- 64/64 Tests bestanden (11 neue)

**Smoke-Test (V0, 5-Fragen-Bundle aus AP-4.2, gpt-4o als Judge):**

| Metrik | Mittelwert | n |
|--------|------------|---|
| Faithfulness | 0.917 | 5 |
| Answer Relevance | 0.863 | 5 |
| Context Precision | 0.720 | 5 |

| Kategorie | n | Faithfulness | Answer Relevance | Context Precision |
|-----------|---|---|---|---|
| Chunking | 2 | 1.000 | 0.861 | 0.933 |
| Recency | 1 | 1.000 | 0.894 | 0.200 |
| Visuals | 1 | 0.968 | 0.848 | 1.000 |
| CrossSource | 1 | 0.615 | 0.853 | 0.533 |

**Befunde:**
- Faithfulness hoch (0.917): V0-Generator halluziniert wenig relativ zum
  abgerufenen Kontext – aber Kontext selbst ist ggf. nicht ideal (V0)
- Context Precision Recency (0.200): Erwartungsgemäss tief – V0 ohne
  Recency-Prior ruft thematisch-ähnliche aber nicht zeitlich-relevante
  Chunks ab; wird in V2 adressiert
- CrossSource Faithfulness (0.615): Tiefster Wert; Fragen über mehrere
  Quellen liegen ausserhalb des V0-Abdeckungsbereichs
- Vollständiger V0-Lauf über 50 Fragen zufällig mitgestartet (CLI-Bug):
  674.6s, ~0.437 USD Runner-Kosten; Bundle in
  `runs/eval/v0/responses_<ts>.jsonl` persistiert (kann für V0-Report
  genutzt werden)

---

## 2026-05-08 – AP-4.2: Runner für die RAGAS-Evaluation

- `src/rag/evaluate/runner.py`: Bundle-Generator für RAGAS-Eval
  - `run_testset(questions, variant, output_path)`: zeilenweise JSONL-
    Persistierung, fehlerresilient (>50% Fehler → Abbruch via RuntimeError)
  - `_select_dry_run_subset()`: stratifiziert 5 Fragen über alle 4 Kategorien
    (Chunking 2×, Recency/Visuals/CrossSource je 1×); deterministisch
  - `_aggregate_stats()`: summiert Token-Counts und schätzt LLM-Kosten
  - `BundleEntry`-Dataclass: question_id, category, result, error
- `scripts/Pipeline/04_evaluate.py`: CLI mit --variant, --dry-run, --verbose
  (ersetzt den alten `ragas_eval`-Stub)
- `tests/test_runner.py`: 8 Tests mit `answer_query`-Mock (kein API-Call)
- Output-Schema: `runs/eval/<variant>/responses_<ts>.jsonl`
  - Hülle: question_id, category, result (= answer_query-Dict), error
- 53/53 Tests bestanden (8 neue)

**Smoke-Test (--dry-run, V0):**

| Aspekt | Wert |
|--------|------|
| Anzahl Fragen | 5 (Q001, Q002, Q026, Q036, Q046) |
| Erfolgreiche Antworten | 5/5 |
| Geschätzte Kosten | ~0.0475 USD |
| Gesamtdauer | 30.8 s |
| Bundle-Datei | `runs/eval/v0/responses_2026-05-08T09-58-07.jsonl` |

---

## 2026-05-08 – AP-4.1: Test-Set-Modul für die RAGAS-Evaluation

- `src/rag/evaluate/__init__.py`: Modul-Docstring mit Stub-Hinweisen für AP-4.2/4.3
- `src/rag/evaluate/testset.py`: Loader, Validator, Iter-Funktionen
  - `load_testset(path)`: JSONL-Loader mit Zeilennummer in Fehlermeldungen
  - `validate_entry(entry, line_number)`: Strenge Validierung (ID-Format, Pflichtfelder,
    Kategorie-Whitelist), zusätzliche Felder werden ignoriert (Vorwärtskompatibilität)
  - `iter_by_category(questions)`: Gruppierung in Canonical-Reihenfolge
  - `_check_consistency(questions)`: Warnungen bei Duplikaten / ID-Lücken (kein Abbruch)
- `src/rag/config.py`: `TESTSET_PATH` ergänzt (variantenunabhängig unter `data/eval/`)
- `data/eval/testset_v1.jsonl`: 50 Fragen, 4 Kategorien
  (Chunking 25, Recency 10, Visuals 10, CrossSource 5)
  Korrektur: ungültiger JSON-Escape `\ ` in Q016 behoben
- `tests/test_testset.py`: 13 Tests, alle ohne API-Calls
- `pyproject.toml`: `filterwarnings` für `PytestCollectionWarning` ergänzt
  (pytest versucht `TestQuestion`-Dataclass als Testklasse zu sammeln)
- 45/45 Tests bestanden

---

## 2026-05-02 – AP-3.1: V0 End-to-End (Retrieval + Generation)

- `src/rag/retrieve/retriever.py`: `retrieve_chunks()` mit cosine-to-similarity-
  Konvertierung (`similarity = 1 - distance`); ChromaDB-IDs werden automatisch
  zurückgegeben (nicht in `include` angegeben – ChromaDB 1.5.8 API)
- `src/rag/generate/prompts.py`: `build_messages()` mit Chunk-Header
  `[source_file: X, chunk_index: N]` und Zitations-Instruktion in System-Message
- `src/rag/generate/llm.py`: `call_llm()` mit Token-Tracking und Dauer-Messung
- `src/rag/generate/pipeline.py`: `answer_query()` orchestriert Retrieval →
  Prompt-Aufbau → LLM-Aufruf; gibt vollständiges JSON-Output-Schema zurück
- `scripts/Pipeline/03_query.py`: CLI mit `--query`, `--variant`, `--no-save`;
  speichert Ergebnis in `runs/<variant>/queries/<ts>_<slug>.json`
- `tests/test_retrieval_and_prompts.py`: 4 Unit-Tests (pure, kein Index nötig)
  + 1 Integration-Test (skippt ohne V0-Index)
- 32/32 Tests bestanden

**Smoke-Tests (Variante v0, TOP_K=5, gpt-4.1):**

| # | Frage | top sim | in tok | out tok | s |
|---|-------|---------|--------|---------|---|
| 1 | Wie lege ich einen neuen Kunden im SelectLine Auftrag an? | 0.3789 | 1561 | 135 | 3.2 |
| 2 | Was tun, wenn der OPOS EZV-Import bei Bezugsteuer einen Fehler wirft? | 0.2542 | 1422 | 263 | 3.5 |
| 3 | Wie kann ich Makros nachträglich aktivieren? | 0.2107 | 2081 | 183 | 2.1 |

**Befunde:**
- Similaritätswerte generell niedrig (0.21–0.38): V0-Naive-Baseline expected;
  ohne Metadaten-Filterung oder Reranking liefert die naive Suche suboptimale Matches
- Zitation `[Quelle: unknown, Chunk 0]` erscheint bei Fragen 1 & 2: LLM nutzt
  das Zitations-Format, aber `source_file`-Metadaten aus dem Ticket/Forum-Quellen
  enthalten keinen Dateinamen → als "unknown" ausgegeben. Muss in V1+ adressiert werden.
- Frage 3 ("Makros"): korrekte Quellennennung `[Schulungsunterlagen Makroassistent.pdf, Chunk 2]`

---

## 2026-05-02 – AP-3: V0-Indexierung auf Vollumfang

- `CHUNK_SIZE` auf 1000, `CHUNK_OVERLAP` auf 150 gesetzt (DE-4)
- `src/rag/index/chunking.py`: V0-Chunker mit tiktoken (`cl100k_base`),
  quelltypagnostisch; liest `content.full_text`; Chunk-IDs mit `source_type`-
  Prefix zur Vermeidung von Kollisionen bei gleichen Dateinamen in
  verschiedenen Quellen
- `src/rag/index/embeddings.py`: `embed_chunks()` mit Batch-Logging
- `src/rag/index/vectorstore.py`: `get_or_create_collection()` + `add_chunks_to_collection()`
- `src/rag/pipeline_factory.py`: `get_chunker("v0")` implementiert
- `scripts/Pipeline/02_index.py`: Orchestrierung über alle fünf Gold-Quellen,
  `--reset` und `--max-chunks N` Flags, Kosten-Schätzung im Log
- Indexierung Vollumfang:
  - forum.jsonl:              2'052 Einträge →  2'303 Chunks
  - tickets.jsonl:            4'691 Einträge →  4'867 Chunks
  - handbuecher.jsonl:            8 Einträge →  3'814 Chunks
  - modulbeschreibungen.jsonl:   63 Einträge →    469 Chunks
  - schulungsunterlagen.jsonl:   19 Einträge →    336 Chunks
  - Total: 11'789 Chunks im Index (`data/index/v0/`)
  - Embedding-Kosten: ~0.82 USD (text-embedding-3-large, 6.34M Tokens)
  - Dauer: 29.3 Minuten
- 27/27 Tests bestanden (4 neue Chunking-Tests)
- Befund: "Jahresabschluss und Zwischenabschluss SelectLine.pdf" liegt in
  sowohl modulbeschreibungen/ als auch schulungsunterlagen/ → gleiche doc_id;
  gelöst durch source_type-Prefix in Chunk-IDs

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
