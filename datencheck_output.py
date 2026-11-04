"""Kernlogik für den unabhängigen klassifizierten Datencheck."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any

import pandas as pd


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = application_root()
RULES_FILE = ROOT / "datencheck_regeln.json"
CATALOG_FILE = ROOT / "FEHLERKLASSIFIZIERUNG.csv"
OUTPUT_FILE = ROOT / "datencheck_output_01.xlsx"
DEFAULT_IGNORED_SHEETS = {"Uebersicht", "Feldlegende"}


def load_rules(rules_file: Path) -> dict[str, Any]:
    if not rules_file.exists():
        return {}
    with rules_file.open(encoding="utf-8") as file:
        return json.load(file)


def load_catalog(catalog_file: Path) -> pd.DataFrame:
    if not catalog_file.exists():
        raise FileNotFoundError(f"Klassifizierungskatalog fehlt: {catalog_file}")
    return pd.read_csv(catalog_file, sep=";", encoding="utf-8")


def find_header_row(file_path: Path, sheet_name: str) -> int:
    preview = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=15)
    best_row, best_score = 0, -1
    for row_number, row in preview.iterrows():
        values = [str(value).strip() for value in row if pd.notna(value)]
        if not values:
            continue
        score = len(values)
        if any(value.lower().startswith("unnamed:") for value in values):
            score -= 2
        if score > best_score:
            best_row, best_score = int(row_number), score
    return best_row


def read_data(file_path: Path, sheet_name: str) -> tuple[pd.DataFrame, int]:
    header_row = find_header_row(file_path, sheet_name)
    data = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
    data = data.dropna(axis=1, how="all").copy()
    data.columns = [
        str(column).strip()
        if not str(column).startswith("Unnamed:")
        else f"Spalte_{index + 1}"
        for index, column in enumerate(data.columns)
    ]
    return data, header_row


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


def object_name(file_name: str, sheet_name: str) -> str:
    return sheet_name


def system_name(file_name: str, sheet_name: str) -> str:
    if "Stammdaten_MARC" in file_name:
        return "SAP"
    if "HubSpot" in file_name:
        return "HubSpot"
    if "Salesforce" in file_name:
        return "Salesforce"
    return "Unbekannt"


def infer_object(data: pd.DataFrame, file_name: str, sheet_name: str) -> str:
    """Erkennt den Datentyp über Spaltennamen statt über einen Dateinamen."""
    columns = {normalize(column).replace("_", "") for column in data.columns}
    if {"matnr", "mtart"}.issubset(columns):
        if "ersatz" in normalize(sheet_name) or "ersa" in normalize(sheet_name):
            return "MARC-ERSA"
        if "fert" in normalize(sheet_name) or "fert" in normalize(file_name):
            return "MARC-FERT"
        return "MARA"
    signatures = [
        ({"pricebookentryid", "pricebook2id"}, "PricebookEntry"),
        ({"pricebookid", "hspriceeuur"}, "Price Book Items"),
        ({"pricebook2id", "name"}, "Pricebook2"),
        ({"workordernumber", "status"}, "WorkOrder"),
        ({"assetid", "serialnumber"}, "Asset"),
        ({"contactid", "email"}, "Contact"),
        ({"accountid", "name"}, "Account"),
        ({"productcode", "stockkeepingunit"}, "Product2"),
        ({"hsobjectid", "hssku"}, "Products"),
    ]
    for signature, name in signatures:
        if signature.issubset(columns):
            return name
    return sheet_name


def infer_system(data: pd.DataFrame, file_name: str, sheet_name: str) -> str:
    """Erkennt das Quellsystem über Spaltenpräfixe und Feldnamen."""
    columns = {normalize(column).replace("_", "") for column in data.columns}
    if any(column.startswith("hs") for column in columns):
        return "HubSpot"
    if any(column.endswith("__c") for column in columns) or "salesforce" in normalize(file_name):
        return "Salesforce"
    if {"matnr", "mtart"}.issubset(columns):
        return "SAP"
    return system_name(file_name, sheet_name)


def department_for(file_name: str, rules: dict[str, Any]) -> str:
    for fragment, department in rules.get("department_by_file", {}).items():
        if fragment.casefold() in file_name.casefold():
            return department
    return rules.get("default_department", "Datenmanagement (MDM)")


def classification_for(
    catalog: pd.DataFrame,
    *,
    file_name: str,
    sheet_name: str,
    issue_type: str,
    column: str | None,
    data: pd.DataFrame,
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Ordnet einen technischen Befund einem Katalogbefund zu."""
    config = rules.get("classification", {})
    overrides = config.get("overrides", {})
    override = overrides.get(issue_type, {})
    wanted_class = config.get("issue_type_class", {}).get(issue_type)
    obj = infer_object(data, file_name, sheet_name)
    system = infer_system(data, file_name, sheet_name)
    candidates = catalog
    object_aliases = config.get("object_aliases", {}).get(sheet_name, [obj])
    if "Objekt" in catalog:
        object_mask = catalog["Objekt"].astype(str).isin(object_aliases)
        candidates = catalog[object_mask]
    if candidates.empty:
        candidates = pd.DataFrame()
    if wanted_class and "Klasse" in candidates:
        class_candidates = candidates[candidates["Klasse"].astype(str).str.contains(
            wanted_class, case=False, na=False
        )]
        if not class_candidates.empty:
            candidates = class_candidates
    if system != "Unbekannt" and "SYSTEM" in candidates and len(candidates) > 1:
        system_candidates = candidates[candidates["SYSTEM"].astype(str).str.casefold() == system.casefold()]
        if not system_candidates.empty:
            candidates = system_candidates
    if column and not candidates.empty and "Felder" in candidates:
        field_candidates = candidates[candidates["Felder"].astype(str).str.casefold().str.contains(
            re.escape(column.casefold()), na=False
        )]
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


def priority_for(classification: dict[str, Any], issue_type: str, column: str | None,
                 rules: dict[str, Any]) -> str:
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


def add_issue(issues: list[dict[str, Any]], *, file_path: Path, sheet_name: str,
              data: pd.DataFrame, header_row: int, issue_type: str, index: int | None,
              column: str | None, value: Any, suggestion: str,
              rules: dict[str, Any], catalog: pd.DataFrame) -> None:
    classification = classification_for(
        catalog, file_name=file_path.name, sheet_name=sheet_name,
        issue_type=issue_type, column=column, data=data, rules=rules,
    )
    issues.append({
        "id": source_id(data, index),
        "Datei": file_path.name,
        "Datensatz": sheet_name,
        "Erkanntes Objekt": infer_object(data, file_path.name, sheet_name),
        "Excel-Zeile": index + header_row + 2 if index is not None else None,
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
        "Abteilung": department_for(file_path.name, rules),
        "Wert": clean(value),
        "Vorschlag": suggestion,
    })


def check_sheet(file_path: Path, sheet_name: str, rules: dict[str, Any],
                catalog: pd.DataFrame) -> list[dict[str, Any]]:
    data, header_row = read_data(file_path, sheet_name)
    issues: list[dict[str, Any]] = []
    required = set(rules.get("required_columns", {}).get(sheet_name, []))
    for column in required:
        if column not in data.columns:
            add_issue(issues, file_path=file_path, sheet_name=sheet_name, data=data,
                      header_row=header_row, issue_type="Fehlende Spalte", index=None,
                      column=column, value=None, suggestion="Spalte ergänzen.",
                      rules=rules, catalog=catalog)
            continue
        for index, value in data[column].items():
            if pd.isna(value) or (isinstance(value, str) and not value.strip()):
                add_issue(issues, file_path=file_path, sheet_name=sheet_name, data=data,
                          header_row=header_row, issue_type="Fehlender Wert", index=int(index),
                          column=column, value=value,
                          suggestion="Wert ergänzen oder als optional dokumentieren.",
                          rules=rules, catalog=catalog)

    for column in data.columns:
        series = data[column].dropna()
        if series.empty:
            continue
        lower = column.casefold()
        if series.map(lambda value: isinstance(value, str)).any():
            normalized = series.map(normalize)
            for key, group in series.groupby(normalized):
                variants = sorted({str(value) for value in group})
                if key and len(variants) > 1:
                    for index in group.index:
                        add_issue(issues, file_path=file_path, sheet_name=sheet_name,
                                  data=data, header_row=header_row,
                                  issue_type="Schreibvariante", index=int(index),
                                  column=column, value=data.at[index, column],
                                  suggestion=f"Schreibweise vereinheitlichen, z. B. '{variants[0]}'.",
                                  rules=rules, catalog=catalog)
            for index, value in series.items():
                if isinstance(value, str) and value != value.strip():
                    add_issue(issues, file_path=file_path, sheet_name=sheet_name,
                              data=data, header_row=header_row,
                              issue_type="Überflüssige Leerzeichen", index=int(index),
                              column=column, value=value,
                              suggestion="Leerzeichen entfernen.", rules=rules, catalog=catalog)
        looks_like_key = lower in {
            "id", "code", "sku", "productcode", "stockkeepingunit", "hs_object_id"
        } or "materialnummer" in lower or lower == "matnr"
        if looks_like_key:
            for index in series.index[series.duplicated(keep=False)]:
                add_issue(issues, file_path=file_path, sheet_name=sheet_name, data=data,
                          header_row=header_row, issue_type="Doppelter Schlüssel",
                          index=int(index), column=column, value=data.at[index, column],
                          suggestion="Schlüssel bereinigen; jeder Wert muss eindeutig sein.",
                          rules=rules, catalog=catalog)
        if "date" in lower or "datum" in lower or "created" in lower:
            parsed = pd.to_datetime(series, format="mixed", errors="coerce")
            for index in series.index[parsed.isna()]:
                add_issue(issues, file_path=file_path, sheet_name=sheet_name,
                          data=data, header_row=header_row, issue_type="Ungültiges Datum",
                          index=int(index), column=column, value=data.at[index, column],
                          suggestion="Datum im Format YYYY-MM-DD speichern.",
                          rules=rules, catalog=catalog)
        allowed = rules.get("allowed_values", {}).get(column)
        if allowed:
            allowed_normalized = {normalize(value) for value in allowed}
            for index, value in series.items():
                if normalize(value) not in allowed_normalized:
                    add_issue(issues, file_path=file_path, sheet_name=sheet_name,
                              data=data, header_row=header_row,
                              issue_type="Unbekannter Wert", index=int(index),
                              column=column, value=value,
                              suggestion=f"Erlaubte Werte: {', '.join(sorted(allowed))}.",
                              rules=rules, catalog=catalog)
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


def run_check(input_dir: Path, output_file: Path | None = None,
              rules_file: Path = RULES_FILE, catalog_file: Path = CATALOG_FILE) -> Path:
    if output_file is None:
        output_file = input_dir / "datencheck_output_01.xlsx"
    if not rules_file.exists():
        rules_file = ROOT / "datencheck_regeln.json"
    if not catalog_file.exists():
        catalog_file = ROOT / "FEHLERKLASSIFIZIERUNG.csv"
    rules = load_rules(rules_file)
    catalog = load_catalog(catalog_file)
    ignored = set(rules.get("ignored_sheets", DEFAULT_IGNORED_SHEETS))
    input_files = sorted(
        path for path in input_dir.glob("*.xlsx")
        if not path.name.startswith("~$")
        and not path.stem.casefold().startswith("datencheck_ergebnis")
        and not path.stem.casefold().startswith("datencheck_output")
    )
    if not input_files:
        raise FileNotFoundError(f"Keine Excel-Eingabedatei in {input_dir} gefunden.")
    issues: list[dict[str, Any]] = []
    for file_path in input_files:
        with pd.ExcelFile(file_path) as excel_file:
            for sheet_name in excel_file.sheet_names:
                if sheet_name not in ignored:
                    issues.extend(check_sheet(file_path, sheet_name, rules, catalog))
    columns = [
        "id", "Datei", "Datensatz", "Erkanntes Objekt", "Excel-Zeile", "Spalte", "Prüfung",
        "Fehlerklassifizierung", "Fehlerbeschreibung", "Fehlerklasse", "DQ",
        "Ebene", "Schwere", "Impact", "Owner", "Fehlerpriorität", "Abteilung",
        "Wert", "Vorschlag",
    ]
    result = pd.DataFrame(issues, columns=columns)
    if result.empty:
        result = pd.DataFrame([{
            column: "" for column in columns
        }])
        result.loc[0, "Prüfung"] = "Keine Auffälligkeiten"
        result.loc[0, "Fehlerpriorität"] = "ignorieren"
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="Übersicht", index=False)
        used = {"Übersicht", "Katalog"}
        for dataset, frame in result.groupby("Datensatz", dropna=False):
            frame.to_excel(writer, sheet_name=safe_sheet_name(str(dataset), used), index=False)
        catalog.to_excel(writer, sheet_name="Katalog", index=False)
    return output_file
