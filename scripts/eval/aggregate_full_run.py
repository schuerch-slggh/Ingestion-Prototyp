"""Aggregat-Auswertung des Vollauf-Evals.

Liest pro Variante die letzten Bundle-Dateien aus runs/eval/<variante>/
und erzeugt:
- aggregate_metrics.md / .csv (Mittelwerte pro Metrik pro Variante)
- category_breakdown.md / .csv (Aufschlüsselung pro Kategorie)
- pairwise_deltas.md / .csv (Differenzen V0->V1, V1->V2, V2->V3, V2->V4)
- latencies.csv
- diagrams/*.png

Output landet in runs/eval/aggregate/full_run_<datum>/

Metrik-Keys im scorer-Output (ragas_*.json):
    faithfulness, answer_relevance, context_recall, factual_correctness
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EVAL_DIR = Path("runs/eval")
OUTPUT_DIR = EVAL_DIR / "aggregate" / f"full_run_{datetime.now():%Y-%m-%d}"
DIAGRAMS_DIR = OUTPUT_DIR / "diagrams"

VARIANTS = ["v0", "v1", "v2", "v3", "v4"]

# Tupel (json_key, display_label)
METRICS = [
    ("faithfulness", "Faithfulness"),
    ("answer_relevance", "Answer Relevance"),
    ("context_recall", "Context Recall"),
    ("factual_correctness", "Factual Correctness"),
]


def load_latest_bundle(variant: str) -> tuple[list[dict], list[dict]]:
    """Lädt die jüngsten responses_*.jsonl und ragas_*.json einer Variante.

    Returns:
        Tupel (responses, scores_list).
    """
    variant_dir = EVAL_DIR / variant
    response_files = sorted(variant_dir.glob("responses_*.jsonl"))
    ragas_files = sorted(variant_dir.glob("ragas_*.json"))

    if not response_files or not ragas_files:
        raise FileNotFoundError(f"Keine Bundles für {variant} gefunden")

    responses = [
        json.loads(line)
        for line in response_files[-1].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    payload = json.loads(ragas_files[-1].read_text(encoding="utf-8"))
    scores = payload["scores"]

    return responses, scores


def compute_aggregates(all_data: dict[str, tuple]) -> pd.DataFrame:
    """Berechnet pro Variante den Mittelwert jeder Metrik."""
    rows = []
    for variant in VARIANTS:
        if variant not in all_data:
            continue
        _, scores = all_data[variant]
        row = {"Variante": variant.upper()}
        for key, label in METRICS:
            values = [s[key] for s in scores if s.get(key) is not None]
            row[label] = round(mean(values), 4) if values else None
        rows.append(row)
    return pd.DataFrame(rows)


def compute_category_breakdown(
    all_data: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Berechnet pro Variante und Kategorie den Mittelwert pro Metrik.

    Returns:
        Tupel (means_df, counts_df) – means_df enthält Mittelwerte,
        counts_df enthält (n_valid, n_total) als String "n/N" pro Zelle,
        um sparse Zellen transparent zu machen.
    """
    rows_mean = []
    rows_count = []

    for variant in VARIANTS:
        if variant not in all_data:
            continue
        _, scores = all_data[variant]

        # Sammle alle Werte und Gesamtzählungen pro Kategorie
        cat_all: dict[str, dict[str, list]] = defaultdict(
            lambda: {key: [] for key, _ in METRICS}
        )
        cat_valid: dict[str, dict[str, list]] = defaultdict(
            lambda: {key: [] for key, _ in METRICS}
        )
        for s in scores:
            cat = s.get("category", "unknown")
            for key, _ in METRICS:
                cat_all[cat][key].append(s.get(key))
                if s.get(key) is not None:
                    cat_valid[cat][key].append(s[key])

        for cat in cat_all:
            row_mean = {"Variante": variant.upper(), "Kategorie": cat}
            row_count = {"Variante": variant.upper(), "Kategorie": cat}
            for key, label in METRICS:
                valid = cat_valid[cat].get(key, [])
                total = len(cat_all[cat].get(key, []))
                row_mean[label] = round(mean(valid), 4) if valid else None
                row_count[label] = f"{len(valid)}/{total}"
            rows_mean.append(row_mean)
            rows_count.append(row_count)

    return pd.DataFrame(rows_mean), pd.DataFrame(rows_count)


def compute_latencies(all_data: dict) -> pd.DataFrame:
    """Sammelt Latenzen (ms) pro Variante aus den Response-Bundles."""
    rows = []
    for variant in VARIANTS:
        if variant not in all_data:
            continue
        responses, _ = all_data[variant]
        for r in responses:
            if r.get("result") and r["result"].get("metadata"):
                dur_s = r["result"]["metadata"].get("duration_seconds")
                if dur_s is not None:
                    rows.append(
                        {"Variante": variant.upper(), "latency_ms": dur_s * 1000}
                    )
    return pd.DataFrame(rows)


def compute_pairwise_deltas(aggregate: pd.DataFrame) -> pd.DataFrame:
    """Berechnet Differenzen V0->V1, V1->V2, V2->V3, V2->V4."""
    comparisons = [
        ("V0", "V1", "Quellenspezifisches Chunking"),
        ("V1", "V2", "Hybrid-Suche + Schlüsselwörter"),
        ("V2", "V3", "Recency-Re-Ranking"),
        ("V2", "V4", "Multimodalität"),
    ]
    agg_idx = aggregate.set_index("Variante")
    rows = []
    for base, target, label in comparisons:
        if base not in agg_idx.index or target not in agg_idx.index:
            continue
        row = {"Vergleich": f"{base} → {target}", "Erweiterung": label}
        for _, metric_label in METRICS:
            try:
                b = agg_idx.loc[base, metric_label]
                t = agg_idx.loc[target, metric_label]
                row[f"Δ {metric_label}"] = (
                    round(t - b, 4) if b is not None and t is not None else None
                )
            except (KeyError, TypeError):
                row[f"Δ {metric_label}"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def write_markdown_aggregate(aggregate: pd.DataFrame, path: Path) -> None:
    lines = [
        "# Aggregat-Metriken pro Variante",
        "",
        "Mittelwert der RAGAS-Metriken über alle 40 Test-Fragen.",
        "",
        aggregate.to_markdown(index=False, floatfmt=".4f"),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_markdown_category(
    category_df: pd.DataFrame, counts_df: pd.DataFrame, path: Path
) -> None:
    lines = [
        "# Kategorieweise Aufschlüsselung",
        "",
        "Mittelwert der RAGAS-Metriken pro Variante und Kategorie.",
        "Zellen mit `–` / `nan` haben keine validen Scores für diese Kombination.",
        "",
    ]

    # Sammle sparse Zellen für Fussnoten (n_valid < n_total)
    footnotes: list[str] = []

    for _, label in METRICS:
        if label not in category_df.columns:
            continue
        lines.append(f"## {label}")
        lines.append("")
        pivot = category_df.pivot(
            index="Variante", columns="Kategorie", values=label
        )
        lines.append(pivot.to_markdown(floatfmt=".4f"))
        lines.append("")

        # Sparse-Zellen für diese Metrik erfassen
        if label in counts_df.columns:
            for _, row in counts_df.iterrows():
                count_str = row[label]
                n_valid, n_total = (int(x) for x in count_str.split("/"))
                if 0 < n_valid < n_total:
                    footnotes.append(
                        f"- **{row['Variante']}/{row['Kategorie']}/{label}**: "
                        f"{n_valid}/{n_total} valide Werte "
                        f"(Mittelwert aus {n_valid} Fragen)"
                    )
                elif n_valid == 0 and n_total > 0:
                    footnotes.append(
                        f"- **{row['Variante']}/{row['Kategorie']}/{label}**: "
                        f"0/{n_total} valide Werte – RAGAS konnte keinen Score "
                        f"berechnen (Antworten ohne prüfbare Aussagen)"
                    )

    if footnotes:
        # Deduplizieren (gleiche Zelle kann mehrfach auftauchen)
        seen: set[str] = set()
        unique_notes = [n for n in footnotes if not (n in seen or seen.add(n))]
        lines.append("## Anmerkungen zu fehlenden Scores (sparse Zellen)")
        lines.append("")
        lines.extend(unique_notes)
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_markdown_deltas(deltas: pd.DataFrame, path: Path) -> None:
    lines = [
        "# Paarweise Differenzen (Ablation)",
        "",
        "Effekt jeder Erweiterung als Differenz zur Vorgänger-Variante.",
        "",
        deltas.to_markdown(index=False, floatfmt=".4f"),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def plot_bar_metrics(aggregate: pd.DataFrame, out_path: Path) -> None:
    """Bar Chart: 4 Metriken × 5 Varianten."""
    metric_labels = [label for _, label in METRICS]
    variants = aggregate["Variante"].tolist()

    x = np.arange(len(metric_labels))
    width = 0.15

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["#cccccc", "#a8d8ea", "#73b5d6", "#4a90c2", "#2c6fa8"]

    for i, variant in enumerate(variants):
        row = aggregate[aggregate["Variante"] == variant]
        values = [
            row[m].values[0] if row[m].values[0] is not None else 0
            for m in metric_labels
        ]
        ax.bar(x + i * width, values, width, label=variant, color=colors[i])

    ax.set_xlabel("Metrik")
    ax.set_ylabel("Mittlerer Score")
    ax.set_title("RAGAS-Metriken pro Pipeline-Variante (Vollauf, N=40)")
    ax.set_xticks(x + width * (len(variants) - 1) / 2)
    ax.set_xticklabels(metric_labels)
    ax.legend(loc="upper right")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Diagramm: %s", out_path)


def plot_radar(aggregate: pd.DataFrame, out_path: Path) -> None:
    """Radar Chart: ein Pentagon pro Variante mit 4 Metrik-Achsen."""
    metric_labels = [label for _, label in METRICS]
    variants = aggregate["Variante"].tolist()

    angles = np.linspace(0, 2 * np.pi, len(metric_labels), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection="polar"))
    colors = ["#cccccc", "#a8d8ea", "#73b5d6", "#4a90c2", "#2c6fa8"]

    for i, variant in enumerate(variants):
        row = aggregate[aggregate["Variante"] == variant]
        values = [
            row[m].values[0] if row[m].values[0] is not None else 0
            for m in metric_labels
        ]
        values += values[:1]
        ax.plot(angles, values, color=colors[i], linewidth=2, label=variant)
        ax.fill(angles, values, color=colors[i], alpha=0.15)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metric_labels, size=9)
    ax.set_ylim(0, 1.0)
    ax.set_title("Pipeline-Varianten im Vergleich (Radar)", y=1.08)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Diagramm: %s", out_path)


def plot_heatmap(category_df: pd.DataFrame, out_path: Path) -> None:
    """Heatmap: Varianten × Kategorien für Factual Correctness."""
    metric = "Factual Correctness"
    if metric not in category_df.columns:
        logger.warning("Heatmap: Spalte '%s' nicht gefunden, übersprungen.", metric)
        return

    pivot = category_df.pivot(
        index="Variante", columns="Kategorie", values=metric
    ).astype(float)

    fig, ax = plt.subplots(figsize=(10, 5))
    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            value = pivot.values[i, j]
            if not np.isnan(value):
                ax.text(
                    j, i, f"{value:.2f}",
                    ha="center", va="center",
                    color="black" if value > 0.5 else "white",
                )

    ax.set_title(f"Heatmap: {metric} pro Variante und Kategorie")
    plt.colorbar(im, ax=ax, label=metric)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Diagramm: %s", out_path)


def plot_latency_boxplot(latency_df: pd.DataFrame, out_path: Path) -> None:
    """Boxplot der Latenzen pro Variante."""
    if latency_df.empty:
        logger.warning("Latenz-Daten fehlen, Boxplot übersprungen.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    variants_present = [v.upper() for v in VARIANTS if v.upper() in latency_df["Variante"].values]
    data_per_variant = [
        latency_df.loc[latency_df["Variante"] == v, "latency_ms"].values
        for v in variants_present
    ]

    ax.boxplot(data_per_variant, tick_labels=variants_present)
    ax.set_xlabel("Variante")
    ax.set_ylabel("Latenz pro Anfrage [ms]")
    ax.set_title("Latenz-Verteilung pro Pipeline-Variante (Vollauf, N=40)")
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Diagramm: %s", out_path)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)

    all_data: dict[str, tuple] = {}
    for variant in VARIANTS:
        try:
            all_data[variant] = load_latest_bundle(variant)
            _, scores = all_data[variant]
            logger.info("Geladen: %s (%d Scores)", variant, len(scores))
        except FileNotFoundError as exc:
            logger.warning("%s", exc)

    if not all_data:
        logger.error("Keine Bundles gefunden. Abbruch.")
        return

    aggregate = compute_aggregates(all_data)
    aggregate.to_csv(OUTPUT_DIR / "aggregate_metrics.csv", index=False)
    write_markdown_aggregate(aggregate, OUTPUT_DIR / "aggregate_metrics.md")
    logger.info("Aggregat: %s", OUTPUT_DIR / "aggregate_metrics.md")

    category_df, counts_df = compute_category_breakdown(all_data)
    category_df.to_csv(OUTPUT_DIR / "category_breakdown.csv", index=False)
    counts_df.to_csv(OUTPUT_DIR / "category_breakdown_counts.csv", index=False)
    write_markdown_category(category_df, counts_df, OUTPUT_DIR / "category_breakdown.md")
    logger.info("Kategorien: %s", OUTPUT_DIR / "category_breakdown.md")

    deltas = compute_pairwise_deltas(aggregate)
    deltas.to_csv(OUTPUT_DIR / "pairwise_deltas.csv", index=False)
    write_markdown_deltas(deltas, OUTPUT_DIR / "pairwise_deltas.md")
    logger.info("Deltas: %s", OUTPUT_DIR / "pairwise_deltas.md")

    latency_df = compute_latencies(all_data)
    if not latency_df.empty:
        latency_df.to_csv(OUTPUT_DIR / "latencies.csv", index=False)

    plot_bar_metrics(aggregate, DIAGRAMS_DIR / "bar_metrics_per_variant.png")
    plot_radar(aggregate, DIAGRAMS_DIR / "radar_per_variant.png")
    plot_heatmap(category_df, DIAGRAMS_DIR / "heatmap_variant_x_category.png")
    plot_latency_boxplot(latency_df, DIAGRAMS_DIR / "latency_boxplot.png")

    print(f"\nAlle Auswertungen in: {OUTPUT_DIR}")
    print("\n=== Aggregat-Metriken ===")
    print(aggregate.to_string(index=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
