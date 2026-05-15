# Paarweise Differenzen (Ablation)

Effekt jeder Erweiterung als Differenz zur Vorgänger-Variante.

| Vergleich   | Erweiterung                    |   Δ Faithfulness |   Δ Answer Relevance |   Δ Context Recall | Δ Factual Correctness   |
|:------------|:-------------------------------|-----------------:|---------------------:|-------------------:|:------------------------|
| V0 → V1     | Quellenspezifisches Chunking   |           0.0064 |               0.0367 |             0.0159 |                         |
| V1 → V2     | Hybrid-Suche + Schlüsselwörter |          -0.0354 |              -0.0226 |             0.0244 |                         |
| V2 → V3     | Recency-Re-Ranking             |           0.0076 |              -0.0165 |            -0.0512 |                         |
| V2 → V4     | Multimodalität                 |          -0.0148 |               0.0219 |             0.0667 |                         |
