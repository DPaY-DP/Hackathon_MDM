"""Erweiterter Excel-Datencheck mit IDs, Zuständigkeit und Priorität.

Direkter Start:
    python datencheck_neu.py

Regeln werden aus datencheck_regeln.json gelesen. Der Bericht wird nach
Datensatz in einzelne Excel-Reiter aufgeteilt.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
RULES_FILE = ROOT / "datencheck_regeln.json"
OUTPUT_FILE = ROOT / "datencheck_ergebnis_neu.xlsx"
DEFAULT_IGNORED_SHEETS = {"Uebersicht", "Feldlegende"}
DEFAULT_PRIORITY = "kritisch"


def load_rules(rules_file: Path = RULES_FILE) -> dict[str, Any]:
    """Liest die fachlich änderbaren Prüfregeln aus einer JSON-Datei."""
    if not rules_file.exists():
        return {
            "ignored_sheets": list(DEFAULT_IGNORED_SHEETS),
            "default_department": "Datenmanagement (MDM)",
            "department_by_file": {},
            "priority_by_issue": {},
            "required_columns": {},
            "allowed_values": {},
        }
    with rules_file.open(encoding="utf-8") as file:
        return json.load(file)


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


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def excel_value(value: Any) -> Any:
    return None if pd.isna(value) else value


def source_id(data: pd.DataFrame, index: int) -> Any:
    """Ermittelt eine nachvollziehbare Quell-ID für einen Datensatz."""
    candidates = [
        "MATNR",
        "matnr",
        "Materialnummer",
        "ATN_SAP_Materialnummer__c",
        "atn_sap_materialnummer",
        "Id",
        "id",
        "hs_object_id",
        "ProductCode",
        "StockKeepingUnit",
        "hs_sku",
        "sku",
    ]
    for column in candidates:
        if column in data.columns and pd.notna(data.at[index, column]):
            value = data.at[index, column]
            if not (isinstance(value, str) and not value.strip()):
                return value
    return f"Datensatz {index + 1}"


def department_for(file_name: str, rules: dict[str, Any]) -> str:
    for fragment, department in rules.get("department_by_file", {}).items():
        if fragment.casefold() in file_name.casefold():
            return department
    return rules.get("default_department", "Datenmanagement (MDM)")


def add_issue(
    issues: list[dict[str, Any]],
    *,
    file_path: Path,
    sheet_name: str,
    data: pd.DataFrame,
    header_row: int,
    issue_type: str,
    index: int | None,
    column: str | None,
    value: Any,
    suggestion: str,
    rules: dict[str, Any],
) -> None:
    priority = rules.get("priority_by_issue", {}).get(issue_type, DEFAULT_PRIORITY)
    if issue_type == "Doppelter Schlüssel" and column and "matnr" in column.casefold():
        priority = "kritisch"
    issues.append(
        {
            "id": source_id(data, index) if index is not None else "Mehrere Datensätze",
            "Datei": file_path.name,
            "Datensatz": sheet_name,
            "Excel-Zeile": index + header_row + 2 if index is not None else None,
            "Spalte": column,
            "Prüfung": issue_type,
            "Priorität": priority,
            "Abteilung": department_for(file_path.name, rules),
            "Wert": excel_value(value),
            "Vorschlag": suggestion,
        }
    )


def check_sheet(
    file_path: Path, sheet_name: str, rules: dict[str, Any]
) -> list[dict[str, Any]]:
    data, header_row = read_data(file_path, sheet_name)
    issues: list[dict[str, Any]] = []
    required = set(rules.get("required_columns", {}).get(sheet_name, []))
    columns_to_check = required or set(data.columns)

    for column in columns_to_check:
        if column not in data.columns:
            add_issue(
                issues, file_path=file_path, sheet_name=sheet_name, data=data,
                header_row=header_row, issue_type="Fehlende Spalte", index=None,
                column=column, value=None,
                suggestion="Spalte ergänzen oder als optional dokumentieren.",
                rules=rules,
            )
            continue
        for index, value in data[column].items():
            if pd.isna(value) or (isinstance(value, str) and not value.strip()):
                add_issue(
                    issues, file_path=file_path, sheet_name=sheet_name, data=data,
                    header_row=header_row, issue_type="Fehlender Wert", index=int(index),
                    column=column, value=value,
                    suggestion="Wert ergänzen oder als optional dokumentieren.",
                    rules=rules,
                )

    for column in data.columns:
        series = data[column].dropna()
        if series.empty:
            continue
        column_lower = column.casefold()

        if series.map(lambda value: isinstance(value, str)).any():
            normalized = series.map(normalize_text)
            for key, group in series.groupby(normalized):
                variants = sorted({str(value) for value in group})
                if key and len(variants) > 1:
                    for index in group.index:
                        add_issue(
                            issues, file_path=file_path, sheet_name=sheet_name,
                            data=data, header_row=header_row,
                            issue_type="Schreibvariante", index=int(index),
                            column=column, value=data.at[index, column],
                            suggestion=f"Auf eine Schreibweise vereinheitlichen, z. B. '{variants[0]}'.",
                            rules=rules,
                        )
            for index, value in series.items():
                if isinstance(value, str) and value != value.strip():
                    add_issue(
                        issues, file_path=file_path, sheet_name=sheet_name,
                        data=data, header_row=header_row,
                        issue_type="Überflüssige Leerzeichen", index=int(index),
                        column=column, value=value,
                        suggestion="Leerzeichen am Anfang/Ende entfernen.",
                        rules=rules,
                    )

        looks_like_key = column_lower in {
            "id", "code", "sku", "productcode", "stockkeepingunit", "hs_object_id"
        } or "materialnummer" in column_lower or column_lower == "matnr"
        if looks_like_key:
            duplicate_indexes = series.index[series.duplicated(keep=False)]
            for index in duplicate_indexes:
                add_issue(
                    issues, file_path=file_path, sheet_name=sheet_name, data=data,
                    header_row=header_row, issue_type="Doppelter Schlüssel",
                    index=int(index), column=column, value=data.at[index, column],
                    suggestion="Schlüssel bereinigen; jeder Datensatz braucht einen eindeutigen Wert.",
                    rules=rules,
                )

        if "date" in column_lower or "datum" in column_lower or "created" in column_lower:
            parsed = pd.to_datetime(series, format="mixed", errors="coerce")
            for index in series.index[parsed.isna()]:
                add_issue(
                    issues, file_path=file_path, sheet_name=sheet_name, data=data,
                    header_row=header_row, issue_type="Ungültiges Datum", index=int(index),
                    column=column, value=data.at[index, column],
                    suggestion="Datum im Format YYYY-MM-DD speichern.",
                    rules=rules,
                )

        allowed = rules.get("allowed_values", {}).get(column)
        if allowed:
            allowed_normalized = {normalize_text(value) for value in allowed}
            for index, value in series.items():
                if normalize_text(value) not in allowed_normalized:
                    add_issue(
                        issues, file_path=file_path, sheet_name=sheet_name,
                        data=data, header_row=header_row,
                        issue_type="Unbekannter Wert", index=int(index),
                        column=column, value=value,
                        suggestion=f"Erlaubte Werte prüfen: {', '.join(sorted(allowed))}.",
                        rules=rules,
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


def run_check(
    input_dir: Path = ROOT,
    output_file: Path = OUTPUT_FILE,
    rules_file: Path = RULES_FILE,
) -> Path:
    rules = load_rules(rules_file)
    ignored_sheets = set(rules.get("ignored_sheets", DEFAULT_IGNORED_SHEETS))
    input_files = sorted(
        file_path for file_path in input_dir.glob("*.xlsx")
        if not file_path.name.startswith("~$")
        and not file_path.stem.casefold().startswith("datencheck_ergebnis")
    )
    if not input_files:
        raise FileNotFoundError(f"Keine Excel-Datei in {input_dir} gefunden.")

    issues: list[dict[str, Any]] = []
    for file_path in input_files:
        for sheet_name in pd.ExcelFile(file_path).sheet_names:
            if sheet_name not in ignored_sheets:
                issues.extend(check_sheet(file_path, sheet_name, rules))

    columns = [
        "id", "Datei", "Datensatz", "Excel-Zeile", "Spalte", "Prüfung",
        "Priorität", "Abteilung", "Wert", "Vorschlag",
    ]
    result = pd.DataFrame(issues, columns=columns)
    if result.empty:
        result = pd.DataFrame([{
            "id": "", "Datei": "", "Datensatz": "", "Excel-Zeile": "",
            "Spalte": "", "Prüfung": "Keine Auffälligkeiten",
            "Priorität": "ignorieren", "Abteilung": "",
            "Wert": "", "Vorschlag": "Keine Auffälligkeiten gefunden.",
        }])

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="Übersicht", index=False)
        used_names = {"Übersicht", "Legende"}
        for dataset, dataset_result in result.groupby("Datensatz", dropna=False):
            sheet_name = safe_sheet_name(str(dataset), used_names)
            dataset_result.to_excel(writer, sheet_name=sheet_name, index=False)
        pd.DataFrame([
            {"Prüfung": "Doppelter Schlüssel", "Priorität": "kritisch",
             "Bedeutung": "Doppelte Schlüssel, insbesondere MATNR, sofort bereinigen."},
            {"Prüfung": "Schreibvariante", "Priorität": "ignorieren",
             "Bedeutung": "Nur bearbeiten, wenn die Fachabteilung diese Bereinigung später priorisiert."},
            {"Prüfung": "Regeln", "Bedeutung": "Weitere Fehlerquellen in datencheck_regeln.json ergänzen."},
        ]).to_excel(writer, sheet_name="Legende", index=False)
    return output_file


def main() -> None:
    output = run_check()
    print(f"Prüfung abgeschlossen: {output}")


if __name__ == "__main__":
    main()
