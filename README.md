# RAG-Prototyp – Bachelorarbeit

Dieses Repository implementiert einen RAG-Prototypen (Retrieval-Augmented Generation)
als wissenschaftliches Artefakt für eine Bachelorarbeit. Die Pipeline unterstützt
vier Varianten (V0–V3), die kumulativ aufeinander aufbauen.

## Ziel

- Reproduzierbarer RAG-Prototyp mit vier vergleichbaren Varianten
- Saubere Pipeline: Ingest → Index → Retrieve → Generate → Evaluate
- Persistente Artefakte für jeden Schritt
- Variantenspezifische Datenpfade für Vergleichbarkeit

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

Die Pipeline besteht aus vier Skripten in `scripts/Pipeline/`, die sequenziell
ausgeführt werden:

```bash
# 1. Dokumente einlesen und normalisieren
python scripts/Pipeline/01_ingest.py

# 2. Chunks erstellen, Embeddings berechnen, Index aufbauen
python scripts/Pipeline/02_index.py

# 3. Frage stellen und Antwort generieren
python scripts/Pipeline/03_query.py "Deine Frage hier"

# 4. Evaluation durchführen
python scripts/Pipeline/04_evaluate.py
```

## Pipeline-Varianten

Die Pipeline unterstützt vier Varianten, die über `--variant` gewählt werden:

| Variante | Beschreibung | Status |
|----------|--------------|--------|
| `v0` | Naive Baseline – alle Quellen gleich behandelt | Implementiert |
| `v1` | Quellenspezifische Aufbereitung pro Dokumenttyp | Geplant |
| `v2` | Metadaten-Anreicherung & Recency-Prior im Retrieval | Geplant |
| `v3` | Multimodalität via Vision-Language-Model | Geplant |

**Aktuell ist nur V0 implementiert. V1–V3 folgen in nachfolgenden Arbeitspaketen.**

```bash
# Variante explizit angeben
python scripts/Pipeline/02_index.py --variant v0
python scripts/Pipeline/03_query.py --variant v0 "Deine Frage hier"

# Alternativ über Umgebungsvariable (gilt für alle Skripte)
VARIANT=v0 python scripts/Pipeline/02_index.py
```

Jede Variante speichert Artefakte in eigenen Unterordnern:

```
data/processed/v0/   ← Chunks
data/index/v0/       ← Vektorindex
runs/v0/             ← Query-Artefakte
runs/eval/v0/        ← Evaluationsergebnisse
```

## Verzeichnisstruktur

```
data/bronze/         ← Originaldaten (PDFs, CSVs, …)
data/interim/        ← Normalisierter Text (variantenunabhängig)
data/processed/      ← Chunks pro Variante (z. B. processed/v0/)
data/index/          ← Vektorindex pro Variante (z. B. index/v0/)
data/eval/           ← Testdatensatz (variantenunabhängig)
runs/                ← Lauf-Artefakte pro Variante
src/rag/             ← Hauptpaket
scripts/Pipeline/    ← Einstiegspunkte (01_ingest, 02_index, …)
tests/               ← Unit-Tests
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

Dies ist ein wissenschaftlicher Prototyp. V0 dient als Naive-RAG-Baseline;
V1–V3 bauen darauf auf und werden in separaten Arbeitspaketen implementiert.
