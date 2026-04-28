"""
Ticketauswertung – Analyse der Helpdesk-Vorgänge aus vorgaenge.ods

Ausgabe:
  - Konsolenreport mit wichtigsten Kennzahlen
  - data/eval/ticketauswertung_report.txt  – Textzusammenfassung
  - data/eval/tickets_pro_jahr.csv         – Jahresübersicht
  - data/eval/tickets_pro_kategorie.csv    – Häufigste Kategorien
  - data/eval/tickets_pro_produkt.csv      – Häufigste Produkte
"""

import logging
import os
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # Prototyp Alpha/
ODS_FILE = BASE_DIR / "data" / "raw" / "vorgaenge.ods"
EVAL_DIR = BASE_DIR / "data" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Ticketstatus-Namen (Kodierung anpassen falls bekannt)
# ---------------------------------------------------------------------------
TICKETSTATUS_NAMEN: dict[int, str] = {
    1: "Aufgenommen",
    3: "Warten auf Kunde",
    7: "Zu Bearbeiten",
    8: "Zu Testen",
    12: "SLDE",
    13: "Zu Besprechen",
    14: "Warten auf Kunde (zu beobachten)",
    16: "Zu Bearbeiten (nach SLDE)",
    21: "Wiedereröffnet",
    1000: "Erledigt",
}

PRODUKT_NAMEN: dict[float, str] = {
    1.0: "Auftrag",
    2.0: "Rechnungswesen",
    3.0: "Lohn",
    4.0: "Kassabuch",
    5.0: "Leistung",
    6.0: "PC Kasse",
    7.0: "Vertriebsmodul",
    8.0: "Datenorm/Artikelmanager",
    9.0: "WAG Auftrag",
    10.0: "WAG Fibu",
    11.0: "WAG Lohn",
    12.0: "Toolbox",
    13.0: "Systemübergreifend",
    14.0: "Anlagebuchhaltung",
    15.0: "OP-Verwaltung",
    16.0: "Helpdesk",
    17.0: "Internetauftritt",
    18.0: "Verkauf",
    19.0: "Mapkit",
    20.0: "CRM",
    21.0: "SL.mobile",
    22.0: "Plantafel",
    23.0: "/",
    24.0: "Makro SQL",
    25.0: "Power BI",
    26.0: "SL.MDE",
    27.0: "SL.Archiv",
    28.0: "SelectLine Server",
    29.0: "Versand",
    30.0: "Shopware",
}

# ---------------------------------------------------------------------------
# Kategorienamen (laut bekannter Kodierung; anpassen wenn nötig)
# ---------------------------------------------------------------------------
KATEGORIE_NAMEN: dict[float, str] = {
    0.0: "Keine Angabe",
    1000.0: "Auftrag",
    1001.0: "Belege",
    1002.0: "Artikel",
    1003.0: "PKCasse",
    1004.0: "Fibuexport",
    1005.0: "Lager",
    1006.0: "Leistungserfassung",
    1007.0: "SelectLine Mobile",
    1008.0: "Produktion",
    1009.0: "SL.MDE",
    2000.0: "Rechnungswesen",
    2001.0: "Stapelbuchung",
    2002.0: "Kostenrechnung",
    2003.0: "Anlagebuchhaltung",
    2004.0: "MWST",
    3000.0: "OPOS",
    4000.0: "Elektronischer Zahlungsverkehr",
    5000.0: "Lohn",
    5001.0: "Quellensteuer",
    6000.0: "Kassabuch",
    7000.0: "Datenorm/Artikelmanager",
    8000.0: "Toolbox",
    9000.0: "Projekt intern",
    9001.0: "Projektverwaltung",
    10000.0: "Dashboard/Power BI",
    10001.0: "API",
    10002.0: "Paketsdienst",
    10003.0: "SL Easy Cloud",
    10004.0: "SL.Archiv",
    10005.0: "SL.MDE",
    10006.0: "Doqio",
    10007.0: "Versand",
    10008.0: "SelectLine Server",
}


def lade_daten() -> pd.DataFrame:
    """Liest die ODS-Datei und normalisiert Spaltennamen und Typen."""
    log.info("Lade Datei: %s", ODS_FILE)
    df = pd.read_excel(ODS_FILE, engine="odf")
    # Quelldatei-Spalten: ticketnummer, modulbereich, version, beschreibung,
    #                      modul, fehler, loesung, ticketstatus, bearbeitetAm
    df.columns = [
        "ID", "PRODUKTID", "VERSION", "BESCHREIBUNG",
        "KATEGORIE", "FEHLER", "LOESUNG", "TICKETSTATUS", "BEARBEITET",
    ]
    df["BEARBEITET"] = pd.to_datetime(df["BEARBEITET"], errors="coerce")
    df["JAHR"] = df["BEARBEITET"].dt.year.astype("Int64")
    df["MONAT"] = df["BEARBEITET"].dt.to_period("M")
    df["KATEGORIE_NAME"] = df["KATEGORIE"].map(KATEGORIE_NAMEN).fillna(df["KATEGORIE"].apply(
        lambda x: f"Kod. {int(x)}" if pd.notna(x) else "Unbekannt"
    ))
    df["TICKETSTATUS_NAME"] = df["TICKETSTATUS"].map(TICKETSTATUS_NAMEN).fillna(
        df["TICKETSTATUS"].apply(lambda x: f"Status {int(x)}" if pd.notna(x) else "Unbekannt")
    )
    df["PRODUKT_NAME"] = df["PRODUKTID"].map(PRODUKT_NAMEN).fillna(
        df["PRODUKTID"].apply(lambda x: f"Produkt {int(x)}" if pd.notna(x) else "Unbekannt")
    )
    log.info("Geladen: %d Zeilen, %d Spalten", len(df), len(df.columns))
    return df


def grundstatistiken(df: pd.DataFrame) -> dict:
    """Berechnet allgemeine Kennzahlen."""
    total = len(df)
    mit_loesung = df["LOESUNG"].notna().sum()
    ohne_loesung = df["LOESUNG"].isna().sum()
    mit_fehlertext = df["FEHLER"].notna().sum()
    datum_von = df["BEARBEITET"].min()
    datum_bis = df["BEARBEITET"].max()
    jahre = df["BEARBEITET"].dt.year.nunique()
    return {
        "Tickets gesamt": total,
        "Zeitraum von": datum_von.strftime("%d.%m.%Y") if pd.notna(datum_von) else "–",
        "Zeitraum bis": datum_bis.strftime("%d.%m.%Y") if pd.notna(datum_bis) else "–",
        "Anzahl Jahre": jahre,
        "Mit Lösung": f"{mit_loesung} ({mit_loesung / total:.1%})",
        "Ohne Lösung": f"{ohne_loesung} ({ohne_loesung / total:.1%})",
        "Mit Fehlertext": f"{mit_fehlertext} ({mit_fehlertext / total:.1%})",
        "Eindeutige Produkte": int(df["PRODUKT_NAME"].nunique()),
        "Eindeutige Versionen": int(df["VERSION"].nunique()),
        "Eindeutige Kategorien": int(df["KATEGORIE"].nunique()),
        "Eindeutige Ticket-Status": int(df["TICKETSTATUS"].nunique()),
    }


def tickets_pro_jahr(df: pd.DataFrame) -> pd.DataFrame:
    """Anzahl Tickets und Lösungsrate pro Jahr."""
    grp = df.groupby("JAHR", observed=True)
    result = pd.DataFrame({
        "Tickets": grp["ID"].count(),
        "Mit_Loesung": grp["LOESUNG"].apply(lambda s: s.notna().sum()),
    })
    result["Loesungsrate"] = (result["Mit_Loesung"] / result["Tickets"]).map("{:.1%}".format)
    return result.reset_index()


def tickets_pro_kategorie(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """Häufigste Kategorien."""
    grp = df.groupby("KATEGORIE_NAME", observed=True)
    result = pd.DataFrame({
        "Tickets": grp["ID"].count(),
        "Mit_Loesung": grp["LOESUNG"].apply(lambda s: s.notna().sum()),
    }).sort_values("Tickets", ascending=False).head(top_n)
    result["Loesungsrate"] = (result["Mit_Loesung"] / result["Tickets"]).map("{:.1%}".format)
    return result.reset_index()


def tickets_pro_produkt(df: pd.DataFrame) -> pd.DataFrame:
    """Tickets pro Produkt."""
    grp = df.groupby("PRODUKT_NAME", observed=True)
    result = pd.DataFrame({
        "Tickets": grp["ID"].count(),
        "Mit_Loesung": grp["LOESUNG"].apply(lambda s: s.notna().sum()),
    }).sort_values("Tickets", ascending=False)
    result["Loesungsrate"] = (result["Mit_Loesung"] / result["Tickets"]).map("{:.1%}".format)
    return result.reset_index()


def tickets_pro_status(df: pd.DataFrame) -> pd.DataFrame:
    """Tickets pro Ticketstatus – absolut und relativ."""
    total = len(df)
    grp = df.groupby("TICKETSTATUS_NAME", observed=True)
    result = pd.DataFrame({
        "Tickets": grp["ID"].count(),
        "Mit_Loesung": grp["LOESUNG"].apply(lambda s: s.notna().sum()),
    }).sort_values("Tickets", ascending=False)
    result["Anteil_gesamt"] = (result["Tickets"] / total).map("{:.1%}".format)
    result["Loesungsrate"] = (result["Mit_Loesung"] / result["Tickets"]).map("{:.1%}".format)
    return result.reset_index()


def loesung_pro_jahr(df: pd.DataFrame) -> pd.DataFrame:
    """Absolute und relative Anzahl der Tickets mit Lösungsansatz pro Jahr."""
    grp = df.groupby("JAHR", observed=True)
    result = pd.DataFrame({
        "Tickets_gesamt": grp["ID"].count(),
        "Mit_Loesung": grp["LOESUNG"].apply(lambda s: s.notna().sum()),
    })
    total_mit_loesung = result["Mit_Loesung"].sum()
    result["Anteil_am_Jahr"] = (result["Mit_Loesung"] / result["Tickets_gesamt"]).map("{:.1%}".format)
    result["Anteil_an_allen_Loesungen"] = (result["Mit_Loesung"] / total_mit_loesung).map("{:.1%}".format)
    return result.reset_index()


def top_versionen(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Versionen mit den meisten Tickets."""
    return (
        df["VERSION"]
        .value_counts()
        .head(top_n)
        .rename_axis("Version")
        .reset_index(name="Tickets")
    )


def erzeuge_report(
    kenndaten: dict,
    pro_jahr: pd.DataFrame,
    loesung_jahr: pd.DataFrame,
    pro_status: pd.DataFrame,
    pro_kat: pd.DataFrame,
    pro_prod: pd.DataFrame,
    versionen: pd.DataFrame,
) -> str:
    """Erstellt den Textreport als String."""
    lines: list[str] = []

    def h(titel: str) -> None:
        lines.append("")
        lines.append("=" * 60)
        lines.append(f"  {titel}")
        lines.append("=" * 60)

    h("GRUNDSTATISTIKEN")
    for k, v in kenndaten.items():
        lines.append(f"  {k:<30} {v}")

    h("TICKETS PRO JAHR")
    lines.append(pro_jahr.to_string(index=False))

    h("TICKETS MIT LÖSUNGSANSATZ PRO JAHR")
    lines.append("  Anteil_am_Jahr              = Anteil der Tickets mit Lösung an allen Tickets des Jahres")
    lines.append("  Anteil_an_allen_Loesungen   = Anteil dieses Jahres an allen Tickets mit Lösung")
    lines.append(loesung_jahr.to_string(index=False))

    h("TICKETS PRO TICKETSTATUS")
    lines.append("  Anteil_gesamt = Anteil an allen Tickets")
    lines.append("  Loesungsrate  = Anteil mit Lösungsansatz innerhalb des Status")
    lines.append(pro_status.to_string(index=False))

    h(f"TOP {len(pro_kat)} KATEGORIEN")
    lines.append(pro_kat.to_string(index=False))

    h("TICKETS PRO PRODUKT")
    lines.append(pro_prod.to_string(index=False))

    h(f"TOP {len(versionen)} VERSIONEN")
    lines.append(versionen.to_string(index=False))

    return "\n".join(lines)


def main() -> None:
    df = lade_daten()

    log.info("Berechne Kennzahlen …")
    kenndaten = grundstatistiken(df)
    pro_jahr = tickets_pro_jahr(df)
    loesung_jahr = loesung_pro_jahr(df)
    pro_status = tickets_pro_status(df)
    pro_kat = tickets_pro_kategorie(df, top_n=20)
    pro_prod = tickets_pro_produkt(df)
    versionen = top_versionen(df, top_n=10)

    report = erzeuge_report(kenndaten, pro_jahr, loesung_jahr, pro_status, pro_kat, pro_prod, versionen)
    print(report)

    # Artefakte speichern
    report_pfad = EVAL_DIR / "ticketauswertung_report.txt"
    report_pfad.write_text(report, encoding="utf-8")
    log.info("Report gespeichert: %s", report_pfad)

    pro_jahr.to_csv(EVAL_DIR / "tickets_pro_jahr.csv", index=False)
    loesung_jahr.to_csv(EVAL_DIR / "tickets_mit_loesung_pro_jahr.csv", index=False)
    pro_status.to_csv(EVAL_DIR / "tickets_pro_status.csv", index=False)
    pro_kat.to_csv(EVAL_DIR / "tickets_pro_kategorie.csv", index=False)
    pro_prod.to_csv(EVAL_DIR / "tickets_pro_produkt.csv", index=False)
    log.info("CSVs gespeichert in: %s", EVAL_DIR)


if __name__ == "__main__":
    main()
