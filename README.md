# Naive RAG – Baseline-Prototyp (Bachelorarbeit)

Dieses Repository implementiert einen **Naive RAG** (Retrieval-Augmented Generation)
als wissenschaftliche Baseline für eine Bachelorarbeit. Der Prototyp wird
später gegen ein **Modular RAG** evaluiert.

## Ziel

- Einfacher, reproduzierbarer Naive-RAG-Prototyp
- Saubere Pipeline: Ingest → Index → Retrieve → Generate → Evaluate
- Persistente Artefakte für jeden Schritt
- Vergleichsbasis für spätere Modular-RAG-Variante

## Voraussetzungen

- Python ≥ 3.11
- [Ruff](https://docs.astral.sh/ruff/) (Formatter & Linter)
- OpenAI API Key (oder kompatible API)

## Setup

```bash
# Repository klonen
git clone <repo-url>
cd <repo-name>

# Virtuelle Umgebung erstellen
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Dependencies installieren
pip install -e ".[dev]"

# Umgebungsvariablen konfigurieren
cp .env.example .env
# .env mit eigenem API-Key befüllen
```

## Pipeline ausführen

Die Pipeline besteht aus vier Skripten, die sequenziell ausgeführt werden:

```bash
# 1. Dokumente einlesen und normalisieren
python scripts/01_ingest.py

# 2. Chunks erstellen, Embeddings berechnen, Index aufbauen
python scripts/02_index.py

# 3. Frage stellen und Antwort generieren
python scripts/03_query.py "Deine Frage hier"

# 4. Evaluation durchführen
python scripts/04_evaluate.py
```

## Verzeichnisstruktur

```
data/raw/          ← Originaldaten (PDFs, CSVs, …)
data/interim/      ← Zwischenergebnisse (extrahierter Text)
data/processed/    ← Aufbereitete, normalisierte Dokumente
data/index/        ← Vektorindex / Embeddings
data/eval/         ← Evaluationsergebnisse
runs/naive_rag/    ← Lauf-Artefakte des Naive RAG
runs/eval/         ← Evaluations-Runs
src/rag/           ← Hauptpaket
scripts/           ← Einstiegspunkte
tests/             ← Unit-Tests
```

## Tests

```bash
pytest
```

## Linting & Formatting

```bash
ruff check .
ruff format .
```

## Hinweis

Dies ist bewusst eine **einfache Baseline**. Fortgeschrittene RAG-Features
(Re-Ranking, hybride Suche, Agentenlogik etc.) sind nicht enthalten und
werden erst in der Modular-RAG-Variante implementiert.
