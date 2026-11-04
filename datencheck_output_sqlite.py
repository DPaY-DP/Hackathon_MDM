"""Klassifizierter Datencheck gegen die Standalone-SQLite-Datenbank."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from init_db import DB_PATH, get_connection

ProgressCallback = Callable[[Mapping[str, Any]], None]


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = application_root()
RULES_FILE = ROOT / "datencheck_regeln.json"
CATALOG_FILE = ROOT / "FEHLERKLASSIFIZIERUNG.csv"
OUTPUT_FILE = ROOT / "datencheck_output_sqlite_01.xlsx"
DEFAULT_BATCH_SIZE = 5_000
FEHLERLISTE_BATCH_SIZE = 1_000

# Meta-/DQ-Tabellen werden nicht geprüft
SKIP_TABLES = {
    "meta",
    "Fehlerdefinition",
    "Fehlerliste",
    "Fehlerbearbeitung",
    "Beziehung",
    "sqlite_sequence",
}

TABLE_SYSTEM: dict[str, str] = {
    "MARA": "SAP",
    "Produkte_FERT": "SAP",
    "Ersatzteile_ERSA": "SAP",
    "Product2": "Salesforce",
    "Pricebook2": "Salesforce",
    "PricebookEntry": "Salesforce",
    "Account": "Salesforce",
    "Contact": "Salesforce",
    "Asset": "Salesforce",
    "WorkOrder": "Salesforce",
    "Products": "HubSpot",
    "Price_Books": "HubSpot",
    "Price_Book_Items": "HubSpot",
}

# Katalog-Objekt-Aliase (FEHLERKLASSIFIZIERUNG.Objekt)
OBJECT_ALIASES: dict[str, list[str]] = {
    "MARA": ["MARA"],
    "Produkte_FERT": ["MARC-FERT", "Produkte_FERT", "Produkte (FERT)"],
    "Ersatzteile_ERSA": ["MARC-ERSA", "Ersatzteile_ERSA", "Ersatzteile (ERSA)"],
    "Product2": ["Product2"],
    "Pricebook2": ["Pricebook2"],
    "PricebookEntry": ["PricebookEntry"],
    "Account": ["Account"],
    "Contact": ["Contact"],
    "Asset": ["Asset"],
    "WorkOrder": ["WorkOrder"],
    "Products": ["Products"],
    "Price_Books": ["Price Books", "Price_Books"],
    "Price_Book_Items": ["Price Book Items", "Price_Book_Items"],
}

DEFAULT_OBJECT: dict[str, str] = {
    "Produkte_FERT": "MARC-FERT",
    "Ersatzteile_ERSA": "MARC-ERSA",
    "Price_Books": "Price Books",
    "Price_Book_Items": "Price Book Items",
}


def load_rules(rules_file: Path) -> dict[str, Any]:
    if not rules_file.exists():
        return {}
    with rules_file.open(encoding="utf-8") as file:
        return json.load(file)


def load_catalog(catalog_file: Path) -> pd.DataFrame:
    if not catalog_file.exists():
        raise FileNotFoundError(f"Klassifizierungskatalog fehlt: {catalog_file}")
    return pd.read_csv(catalog_file, sep=";", encoding="utf-8")


def list_check_tables(connection: sqlite3.Connection, rules: dict[str, Any]) -> list[str]:
    configured = rules.get("check_tables")
    if configured:
        return [name for name in configured if name not in SKIP_TABLES]
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return [
        name
        for (name,) in rows
        if name not in SKIP_TABLES and not name.startswith("sqlite_")
    ]


def load_table(connection: sqlite3.Connection, table: str) -> pd.DataFrame:
    # Tabellennamen kommen nur aus sqlite_master / Regeln — kein User-Input
    return pd.read_sql_query(f'SELECT * FROM "{table}"', connection)


def table_row_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def _emit(on_progress: ProgressCallback | None, **payload: Any) -> None:
    if on_progress is not None:
        on_progress(payload)


def normalize(value: Any) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def clean(value: Any) -> Any:
    return None if pd.isna(value) else value


def source_id(data: pd.DataFrame, index: int | None) -> Any:
    if index is None:
        return "Mehrere Datensätze"
    candidates = [
        "MATNR", "matnr", "Materialnummer", "ATN_SAP_Materialnummer__c",
        "atn_sap_materialnummer", "Id", "id", "hs_object_id", "ProductCode",
        "StockKeepingUnit", "hs_sku", "sku",
    ]
    for column in candidates:
        if column in data.columns and pd.notna(data.at[index, column]):
            value = data.at[index, column]
            if not isinstance(value, str) or value.strip():
                return value
    return f"Datensatz {index + 1}"


def infer_object(data: pd.DataFrame, table: str) -> str:
    if table in DEFAULT_OBJECT:
        return DEFAULT_OBJECT[table]
    columns = {normalize(column).replace("_", "") for column in data.columns}
    if {"matnr", "mtart"}.issubset(columns):
        lower = normalize(table)
        if "ersa" in lower or "ersatz" in lower:
            return "MARC-ERSA"
        if "fert" in lower:
            return "MARC-FERT"
        return "MARA"
    signatures = [
        ({"pricebook2id", "product2id"}, "PricebookEntry"),
        ({"pricebookid", "hspriceeur"}, "Price Book Items"),
        ({"workordernumber", "status"}, "WorkOrder"),
        ({"serialnumber", "product2id"}, "Asset"),
        ({"firstname", "lastname", "email"}, "Contact"),
        ({"billingcountry", "billingcity"}, "Account"),
        ({"productcode", "stockkeepingunit"}, "Product2"),
        ({"hsobjectid", "hssku"}, "Products"),
        ({"hsname", "hssupportedcurrencies"}, "Price Books"),
        ({"isstandard", "currencyisocode"}, "Pricebook2"),
    ]
    for signature, name in signatures:
        if signature.issubset(columns):
            return name
    return table


def system_for(table: str) -> str:
    return TABLE_SYSTEM.get(table, "Unbekannt")


def department_for(table: str, rules: dict[str, Any]) -> str:
    by_table = rules.get("department_by_table", {})
    if table in by_table:
        return by_table[table]
    system = system_for(table)
    by_system = rules.get("department_by_system", {})
    if system in by_system:
        return by_system[system]
    return rules.get("default_department", "Datenmanagement (MDM)")


def classification_for(
    catalog: pd.DataFrame,
    *,
    table: str,
    issue_type: str,
    column: str | None,
    data: pd.DataFrame,
    rules: dict[str, Any],
) -> dict[str, Any]:
    config = rules.get("classification", {})
    overrides = config.get("overrides", {})
    override = overrides.get(issue_type, {})
    wanted_class = config.get("issue_type_class", {}).get(issue_type)
    obj = infer_object(data, table)
    system = system_for(table)
    candidates = catalog
    object_aliases = config.get("object_aliases", {}).get(
        table, OBJECT_ALIASES.get(table, [obj])
    )
    if "Objekt" in catalog:
        object_mask = catalog["Objekt"].astype(str).isin(object_aliases)
        candidates = catalog[object_mask]
    if candidates.empty:
        candidates = pd.DataFrame()
    if wanted_class and not candidates.empty and "Klasse" in candidates:
        class_candidates = candidates[candidates["Klasse"].astype(str).str.contains(
            wanted_class, case=False, na=False
        )]
        if not class_candidates.empty:
            candidates = class_candidates
    if system != "Unbekannt" and not candidates.empty and "SYSTEM" in candidates and len(candidates) > 1:
        system_candidates = candidates[
            candidates["SYSTEM"].astype(str).str.casefold() == system.casefold()
        ]
        if not system_candidates.empty:
            candidates = system_candidates
    if column and not candidates.empty and "Felder" in candidates:
        field_candidates = candidates[
            candidates["Felder"].astype(str).str.casefold().str.contains(
                re.escape(column.casefold()), na=False
            )
        ]
        if not field_candidates.empty:
            candidates = field_candidates
    selected = candidates.iloc[0].to_dict() if not candidates.empty else {}
    selected.update(override)
    if not selected:
        selected = {
            "ID": config.get("fallback_id", "GEN-001"),
            "Befund": issue_type,
            "Klasse": wanted_class or "FORMAT",
            "DQ": "Gültigkeit",
            "Ebene": "E1",
            "Schwere": "mittel",
            "Impact": "",
            "Owner": "MDM",
        }
    return selected


def priority_for(
    classification: dict[str, Any],
    issue_type: str,
    column: str | None,
    rules: dict[str, Any],
) -> str:
    by_issue = rules.get("priority_by_issue", {})
    if issue_type in by_issue:
        return by_issue[issue_type]
    config = rules.get("classification", {})
    if issue_type in config.get("priority_by_issue", {}):
        return config["priority_by_issue"][issue_type]
    if column and "matnr" in column.casefold() and issue_type == "Doppelter Schlüssel":
        return "kritisch"
    if classification.get("Klasse") == "DUP":
        return "kritisch"
    return config.get("priority_by_severity", {}).get(
        str(classification.get("Schwere", "")).casefold(), "kritisch"
    )


def required_columns_for(table: str, rules: dict[str, Any]) -> set[str]:
    required = rules.get("required_columns", {})
    keys = [table, *OBJECT_ALIASES.get(table, []), DEFAULT_OBJECT.get(table, "")]
    found: set[str] = set()
    for key in keys:
        if key and key in required:
            found.update(required[key])
    return found


def add_issue(
    issues: list[dict[str, Any]],
    *,
    table: str,
    data: pd.DataFrame,
    issue_type: str,
    index: int | None,
    column: str | None,
    value: Any,
    suggestion: str,
    rules: dict[str, Any],
    catalog: pd.DataFrame,
) -> None:
    classification = classification_for(
        catalog,
        table=table,
        issue_type=issue_type,
        column=column,
        data=data,
        rules=rules,
    )
    issues.append({
        "id": source_id(data, index),
        "Datei": system_for(table),
        "Datensatz": table,
        "Erkanntes Objekt": infer_object(data, table),
        "Zeile": index + 1 if index is not None else None,
        "Spalte": column,
        "Prüfung": issue_type,
        "Fehlerklassifizierung": classification.get("ID"),
        "Fehlerbeschreibung": classification.get("Befund"),
        "Fehlerklasse": classification.get("Klasse"),
        "DQ": classification.get("DQ"),
        "Ebene": classification.get("Ebene"),
        "Schwere": classification.get("Schwere"),
        "Impact": classification.get("Impact"),
        "Owner": classification.get("Owner"),
        "Fehlerpriorität": priority_for(classification, issue_type, column, rules),
        "Abteilung": department_for(table, rules),
        "Wert": clean(value),
        "Vorschlag": suggestion,
    })


def _check_required_batch(
    issues: list[dict[str, Any]],
    table: str,
    data: pd.DataFrame,
    batch: pd.DataFrame,
    required: set[str],
    rules: dict[str, Any],
    catalog: pd.DataFrame,
) -> None:
    for column in required:
        if column not in data.columns:
            continue
        for index, value in batch[column].items():
            if pd.isna(value) or (isinstance(value, str) and not value.strip()):
                add_issue(
                    issues, table=table, data=data, issue_type="Fehlender Wert",
                    index=int(index), column=column, value=value,
                    suggestion="Wert ergänzen oder als optional dokumentieren.",
                    rules=rules, catalog=catalog,
                )


def _check_column_batch(
    issues: list[dict[str, Any]],
    table: str,
    data: pd.DataFrame,
    batch: pd.DataFrame,
    column: str,
    rules: dict[str, Any],
    catalog: pd.DataFrame,
) -> None:
    """Zeilenlokale Prüfungen auf einem Batch (ohne Schreibvariante/Duplikate)."""
    if column not in batch.columns:
        return
    series = batch[column].dropna()
    if series.empty:
        return
    lower = column.casefold()
    if series.map(lambda value: isinstance(value, str)).any():
        for index, value in series.items():
            if isinstance(value, str) and value != value.strip():
                add_issue(
                    issues, table=table, data=data,
                    issue_type="Überflüssige Leerzeichen", index=int(index),
                    column=column, value=value,
                    suggestion="Leerzeichen entfernen.",
                    rules=rules, catalog=catalog,
                )
    if "date" in lower or "datum" in lower or "created" in lower:
        parsed = pd.to_datetime(series, format="mixed", errors="coerce")
        for index in series.index[parsed.isna()]:
            add_issue(
                issues, table=table, data=data, issue_type="Ungültiges Datum",
                index=int(index), column=column, value=data.at[index, column],
                suggestion="Datum im Format YYYY-MM-DD speichern.",
                rules=rules, catalog=catalog,
            )
    allowed = rules.get("allowed_values", {}).get(column)
    if allowed:
        allowed_normalized = {normalize(value) for value in allowed}
        for index, value in series.items():
            if normalize(value) not in allowed_normalized:
                add_issue(
                    issues, table=table, data=data, issue_type="Unbekannter Wert",
                    index=int(index), column=column, value=value,
                    suggestion=f"Erlaubte Werte: {', '.join(sorted(allowed))}.",
                    rules=rules, catalog=catalog,
                )


def _check_column_global(
    issues: list[dict[str, Any]],
    table: str,
    data: pd.DataFrame,
    column: str,
    rules: dict[str, Any],
    catalog: pd.DataFrame,
) -> None:
    """Prüfungen über die gesamte Spalte (Schreibvariante, Doppelter Schlüssel)."""
    series = data[column].dropna()
    if series.empty:
        return
    lower = column.casefold()
    if series.map(lambda value: isinstance(value, str)).any():
        normalized = series.map(normalize)
        for key, group in series.groupby(normalized):
            variants = sorted({str(value) for value in group})
            if key and len(variants) > 1:
                for index in group.index:
                    add_issue(
                        issues, table=table, data=data,
                        issue_type="Schreibvariante", index=int(index),
                        column=column, value=data.at[index, column],
                        suggestion=f"Schreibweise vereinheitlichen, z. B. '{variants[0]}'.",
                        rules=rules, catalog=catalog,
                    )
    looks_like_key = lower in {
        "id", "code", "sku", "productcode", "stockkeepingunit", "hs_object_id"
    } or "materialnummer" in lower or lower == "matnr"
    if looks_like_key:
        for index in series.index[series.duplicated(keep=False)]:
            add_issue(
                issues, table=table, data=data, issue_type="Doppelter Schlüssel",
                index=int(index), column=column, value=data.at[index, column],
                suggestion="Schlüssel bereinigen; jeder Wert muss eindeutig sein.",
                rules=rules, catalog=catalog,
            )


def check_table(
    table: str,
    data: pd.DataFrame,
    rules: dict[str, Any],
    catalog: pd.DataFrame,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    on_progress: ProgressCallback | None = None,
    progress_base: float = 0.0,
    progress_span: float = 100.0,
) -> list[dict[str, Any]]:
    """Prüft eine Tabelle in Zeilen-Batches; globale Checks laufen spaltenweise danach."""
    issues: list[dict[str, Any]] = []
    required = required_columns_for(table, rules)
    row_count = len(data)
    columns = list(data.columns)

    for column in required:
        if column not in data.columns:
            add_issue(
                issues, table=table, data=data, issue_type="Fehlende Spalte",
                index=None, column=column, value=None, suggestion="Spalte ergänzen.",
                rules=rules, catalog=catalog,
            )

    if row_count == 0:
        _emit(
            on_progress,
            status="running",
            percent=round(progress_base + progress_span, 1),
            table=table,
            message=f"{table}: leer",
            rows_done=0,
            rows_total=0,
        )
        return issues

    # Phase A (~70 %): zeilenlokale Checks in Batches
    local_span = progress_span * 0.7
    effective_batch = max(1, batch_size)
    for start in range(0, row_count, effective_batch):
        batch = data.iloc[start : start + effective_batch]
        _check_required_batch(issues, table, data, batch, required, rules, catalog)
        for column in columns:
            _check_column_batch(issues, table, data, batch, column, rules, catalog)
        done = min(start + effective_batch, row_count)
        fraction = done / row_count
        _emit(
            on_progress,
            status="running",
            percent=round(progress_base + local_span * fraction, 1),
            table=table,
            message=f"{table}: Batch {done:,}/{row_count:,} Zeilen",
            rows_done=done,
            rows_total=row_count,
            batch_start=start,
            batch_size=len(batch),
        )

    # Phase B (~30 %): Schreibvariante / Doppelter Schlüssel über ganze Spalten
    global_span = progress_span * 0.3
    col_count = max(len(columns), 1)
    for col_index, column in enumerate(columns):
        _check_column_global(issues, table, data, column, rules, catalog)
        fraction = (col_index + 1) / col_count
        _emit(
            on_progress,
            status="running",
            percent=round(progress_base + local_span + global_span * fraction, 1),
            table=table,
            message=f"{table}: Spalte {column} ({col_index + 1}/{col_count})",
            rows_done=row_count,
            rows_total=row_count,
            column=column,
        )
    return issues


def safe_sheet_name(name: str, used_names: set[str]) -> str:
    name = re.sub(r"[\[\]:*?/\\]", "_", name)[:31] or "Datensatz"
    candidate, number = name, 2
    while candidate in used_names:
        suffix = f"_{number}"
        candidate = f"{name[:31 - len(suffix)]}{suffix}"
        number += 1
    used_names.add(candidate)
    return candidate


def known_fehlercodes(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT Fehlercode FROM Fehlerdefinition").fetchall()
    return {str(code) for (code,) in rows}


def _has_table(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def write_fehlerliste(
    connection: sqlite3.Connection,
    issues: list[dict[str, Any]],
    valid_codes: set[str],
) -> int:
    """Schreibt Befunde mit gültigem Katalogcode in Fehlerliste.

    Priorität ``ignorieren`` (z. B. Schreibvariante) bleibt nur im Excel-Bericht,
    damit die DB nicht mit kosmetischen Massenbefunden vollläuft.

    Existiert die App-Tabelle ``Fehlerbearbeitung``, werden Feld und Ist-Wert
    für die Web-Oberfläche mitgeschrieben.
    """
    write_bearbeitung = _has_table(connection, "Fehlerbearbeitung")
    if write_bearbeitung:
        connection.execute("DELETE FROM Fehlerbearbeitung")
    connection.execute("DELETE FROM Fehlerliste")

    rows: list[tuple[Any, ...]] = []
    for issue in issues:
        code = issue.get("Fehlerklassifizierung")
        if not code or str(code) not in valid_codes:
            continue
        if issue.get("Prüfung") == "Keine Auffälligkeiten":
            continue
        if str(issue.get("Fehlerpriorität", "")).casefold() == "ignorieren":
            continue
        ursprungs_id = issue.get("id")
        if ursprungs_id is None or str(ursprungs_id).strip() == "":
            ursprungs_id = "unbekannt"
        feld = issue.get("Spalte")
        wert = issue.get("Wert")
        rows.append((
            str(code),
            str(issue.get("Datensatz") or "unbekannt"),
            str(ursprungs_id),
            None if feld is None or str(feld).strip() == "" else str(feld),
            None if wert is None or str(wert).strip() == "" else str(wert),
        ))

    count = 0
    for start in range(0, len(rows), FEHLERLISTE_BATCH_SIZE):
        chunk = rows[start : start + FEHLERLISTE_BATCH_SIZE]
        for code, tabelle, ursprungs_id, feld, wert in chunk:
            cursor = connection.execute(
                """
                INSERT INTO Fehlerliste (Fehlercode, Ursprungstabelle, Ursprungs_ID)
                VALUES (?, ?, ?)
                """,
                (code, tabelle, ursprungs_id),
            )
            count += 1
            if write_bearbeitung:
                connection.execute(
                    """
                    INSERT INTO Fehlerbearbeitung
                        (Fehlerid, Feld, Ist_Wert, Status)
                    VALUES (?, ?, ?, 'offen')
                    """,
                    (cursor.lastrowid, feld, wert),
                )
        connection.commit()
    return count


def run_check(
    db_path: Path = DB_PATH,
    output_file: Path | None = None,
    rules_file: Path = RULES_FILE,
    catalog_file: Path = CATALOG_FILE,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    on_progress: ProgressCallback | None = None,
) -> Path:
    if output_file is None:
        output_file = OUTPUT_FILE
    if not db_path.exists():
        raise FileNotFoundError(
            f"SQLite-Datenbank fehlt: {db_path}\n"
            "Bitte zuerst install_datencheck.bat bzw. init_db.py + load_data.py ausführen."
        )
    if not rules_file.exists():
        rules_file = ROOT / "datencheck_regeln.json"
    if not catalog_file.exists():
        catalog_file = ROOT / "FEHLERKLASSIFIZIERUNG.csv"

    rules = load_rules(rules_file)
    catalog = load_catalog(catalog_file)
    issues: list[dict[str, Any]] = []

    _emit(
        on_progress,
        status="running",
        percent=0.0,
        table="",
        message="Starte Datencheck …",
        rows_done=0,
        rows_total=0,
    )

    with get_connection(db_path) as connection:
        tables = list_check_tables(connection, rules)
        if not tables:
            raise FileNotFoundError(f"Keine prüfbaren Tabellen in {db_path} gefunden.")

        row_totals = {table: table_row_count(connection, table) for table in tables}
        grand_total = sum(row_totals.values()) or 1
        # 0–92 % Prüfung, 92–96 % Fehlerliste, 96–100 % Excel
        check_span = 92.0
        rows_before = 0

        for table_index, table in enumerate(tables):
            table_rows = row_totals[table]
            weight = table_rows / grand_total if grand_total else 1 / len(tables)
            progress_base = check_span * (rows_before / grand_total)
            progress_span = check_span * weight

            _emit(
                on_progress,
                status="running",
                percent=round(progress_base, 1),
                table=table,
                message=f"Lade {table} ({table_index + 1}/{len(tables)}) …",
                rows_done=rows_before,
                rows_total=grand_total,
                table_index=table_index + 1,
                table_count=len(tables),
            )
            data = load_table(connection, table)
            issues.extend(
                check_table(
                    table,
                    data,
                    rules,
                    catalog,
                    batch_size=batch_size,
                    on_progress=on_progress,
                    progress_base=progress_base,
                    progress_span=progress_span,
                )
            )
            del data
            rows_before += table_rows

        columns = [
            "id", "Datei", "Datensatz", "Erkanntes Objekt", "Zeile", "Spalte", "Prüfung",
            "Fehlerklassifizierung", "Fehlerbeschreibung", "Fehlerklasse", "DQ",
            "Ebene", "Schwere", "Impact", "Owner", "Fehlerpriorität", "Abteilung",
            "Wert", "Vorschlag",
        ]
        result = pd.DataFrame(issues, columns=columns)
        if result.empty:
            result = pd.DataFrame([{column: "" for column in columns}])
            result.loc[0, "Prüfung"] = "Keine Auffälligkeiten"
            result.loc[0, "Fehlerpriorität"] = "ignorieren"
            issues = []

        _emit(
            on_progress,
            status="running",
            percent=93.0,
            table="",
            message="Schreibe Fehlerliste …",
            rows_done=grand_total,
            rows_total=grand_total,
        )
        write_fehlerliste(connection, issues, known_fehlercodes(connection))

    _emit(
        on_progress,
        status="running",
        percent=96.0,
        table="",
        message="Schreibe Excel-Bericht …",
        rows_done=grand_total,
        rows_total=grand_total,
    )
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="Übersicht", index=False)
        used = {"Übersicht", "Katalog"}
        for dataset, frame in result.groupby("Datensatz", dropna=False):
            frame.to_excel(
                writer,
                sheet_name=safe_sheet_name(str(dataset), used),
                index=False,
            )
        catalog.to_excel(writer, sheet_name="Katalog", index=False)

    _emit(
        on_progress,
        status="done",
        percent=100.0,
        table="",
        message=f"Fertig: {output_file.name}",
        rows_done=grand_total,
        rows_total=grand_total,
        output=str(output_file),
        befunde=len(issues),
    )
    return output_file


if __name__ == "__main__":
    def _cli_progress(info: Mapping[str, Any]) -> None:
        percent = info.get("percent", 0)
        message = info.get("message", "")
        print(f"\r[{percent:5.1f}%] {message:<60}", end="", flush=True)
        if info.get("status") == "done":
            print()

    try:
        path = run_check(on_progress=_cli_progress)
    except Exception as error:
        print(f"\nDatencheck fehlgeschlagen: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Bericht erstellt: {path}")
