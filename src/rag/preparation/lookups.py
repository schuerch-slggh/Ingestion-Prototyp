"""Lookup-Tabellen für die Datenaufbereitung."""

import logging

logger = logging.getLogger(__name__)

FORUM_MODULE_LOOKUP: dict[str, str] = {
    "12": "Neue Versionen",
    "15": "SelectLine Auftrag",
    "16": "SelectLine Lohn",
    "17": "V17 USTVADAT keine Anzeige - Lösung",
    "18": "SelectLine Mobile",
    "19": "Plantafel",
    "20": "Programmübergreifend",
    "24": "Installation / Updates",
    "25": "Updates",
    "26": "SQL Server",
    "27": "Abkündigung SQL Server 2008 R2 und Windows Vi",
    "29": "PC-Kasse",
    "34": "Lagerverwaltung",
    "36": "SelectLine Auftrag Allgemein",
    "45": "SelectLine Rechnungswesen / Fibu Allgemein",
    "49": "Kostenrechnung",
    "50": "SQL Server",
    "54": "Verbuchung der Bezugsteuer",
    "56": "ELM: EIV-Upload der XML-Datei per Internet",
    "57": "Skip5",
    "59": "Allgemeine Forum Regel für die Registrierung",
    "68": "Makros",
    "69": "Toolbox & COM",
    "70": "CRM",
    "72": "Off-Topics - Partner-Lösungen",
    "74": "SelectLine stellt sich vor - Rundgang durch's",
    "76": "Off-Topics - Partner-Lösungen",
    "77": "Fremdwährungen im Kassabuch",
    "78": "Programm Einrichtung",
    "79": "Einrichtung Lohn",
    "80": "OPOS EZV Rechnungswesen",
    "81": "Toolbox",
    "82": "SelectLine News",
    "83": "MDE",
    "84": "Doqio",
    "85": "SelectLine Server",
}


PRODUCT_LOOKUP: dict[str, str] = {
    "1": "Auftrag",
    "2": "Rechnungswesen",
    "3": "Lohn",
    "4": "Kassabuch",
    "5": "Leistung",
    "6": "PC Kasse",
    "7": "Vertriebsmodul",
    "8": "Datenorm/Artikelmanager",
    "9": "WAG Auftrag",
    "10": "WAG Fibu",
    "11": "WAG Lohn",
    "12": "Toolbox",
    "13": "Systemübergreifend",
    "14": "Anlagebuchhaltung",
    "15": "OP-Verwaltung",
    "16": "Helpdesk",
    "17": "Internetauftritt",
    "18": "Verkauf",
    "19": "Mapkit",
    "20": "CRM",
    "21": "SL.mobile",
    "22": "Plantafel",
    "23": "/",
    "24": "Makro SQL",
    "25": "Power BI",
    "26": "SL.MDE",
    "27": "SL.Archiv",
    "28": "SelectLine Server",
}

TICKET_STATUS_LOOKUP: dict[str, str] = {
    "1": "Aufgenommen",
    "7": "Zu Bearbeiten",
    "8": "Zu Testen",
    "12": "SLDE",
    "13": "Zu Besprechen",
    "17": "Abgebrochen",
    "21": "Wiedereröffnet",
    "1000": "Erledigt",
}


def resolve_product(product_id: str) -> str:
    """Löst einen PRODUKTID-Code in den Klartext-Produktnamen auf.

    Liegt der Code nicht in der Lookup-Tabelle, wird der Code selbst
    zurückgegeben und eine Warnung geloggt.
    """
    if product_id in PRODUCT_LOOKUP:
        return PRODUCT_LOOKUP[product_id]
    logger.warning(
        "Unbekannte PRODUKTID '%s' – Code wird als Klartext beibehalten", product_id
    )
    return product_id


def resolve_ticket_status(status_id: str) -> str:
    """Löst einen STATUSID-Code in den Klartext-Statusnamen auf.

    Liegt der Code nicht in der Lookup-Tabelle, wird der Code selbst
    zurückgegeben und eine Warnung geloggt.
    """
    if status_id in TICKET_STATUS_LOOKUP:
        return TICKET_STATUS_LOOKUP[status_id]
    logger.warning(
        "Unbekannte STATUSID '%s' – Code wird als Klartext beibehalten", status_id
    )
    return status_id


def resolve_forum_module(forum_id: str) -> str:
    """Löst einen phpBB forum_id-Code in den Klartext-Modulnamen auf.

    Liegt der Code nicht in der Lookup-Tabelle, wird der Code selbst
    zurückgegeben und eine Warnung geloggt.
    """
    if forum_id in FORUM_MODULE_LOOKUP:
        return FORUM_MODULE_LOOKUP[forum_id]
    logger.warning(
        "Unbekannte forum_id '%s' – Code wird als Klartext beibehalten", forum_id
    )
    return forum_id
