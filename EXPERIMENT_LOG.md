# Experiment Log

Pro Eintrag: Datum, Variante, Änderung, beobachteter Effekt.

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
