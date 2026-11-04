"""Prüft Excel-Daten auf fehlende Werte und typische Datenfehler.

Start:
    python datencheck.py

Der Code verarbeitet alle .xlsx-Dateien im gleichen Ordner wie dieses Skript.
Die Ergebnisse werden in "datencheck_ergebnis.xlsx" gespeichert.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
OUTPUT_FILE = ROOT / "datencheck_ergebnis.xlsx"
IGNORED_SHEETS = {"Uebersicht", "Feldlegende"}

# Hier können fachlich verpflichtende Spalten hinterlegt werden. Die Namen
# müssen exakt so geschrieben sein wie die Spaltennamen in der Excel-Datei.
REQUIRED_COLUMNS: dict[str, set[str]] = {
    # Beispiel:
    # "Product2": {"Id", "Name", "ProductCode"},
}

# Hier können erlaubte Werte je Spalte ergänzt werden. Abweichungen werden
# als "unbekannter Wert" gemeldet, aber nicht automatisch geändert.
ALLOWED_VALUES: dict[str, set[str]] = {
    # Beispiel:
    # "IsActive": {"True", "False"},
}


def find_header_row(file_path: Path, sheet_name: str) -> int:
    """Findet die Zeile mit den Feldnamen eines Tabellenblatts."""
    preview = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=15)
    best_row = 0
    best_score = -1

    for row_number, row in preview.iterrows():
        values = [str(value).strip() for value in row if pd.notna(value)]
        if not values:
            continue
        score = len(values)
        if any(value.lower().startswith("unnamed:") for value in values):
            score -= 2
        if score > best_score:
            best_row = int(row_number)
            best_score = score

    return best_row


def read_data(file_path: Path, sheet_name: str) -> pd.DataFrame:
    """Liest ein Datenblatt mit automatisch erkannter Header-Zeile ein."""
    header_row = find_header_row(file_path, sheet_name)
    data = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
    data = data.dropna(axis=1, how="all").copy()
    data.columns = [
        str(column).strip() if not str(column).startswith("Unnamed:") else f"Spalte_{index + 1}"
        for index, column in enumerate(data.columns)
    ]
    return data


def normalize_text(value: Any) -> str:
    """Erzeugt einen Vergleichswert für Schreibweisen."""
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def add_issue(
    issues: list[dict[str, Any]],
    file_name: str,
    sheet_name: str,
    issue_type: str,
    row_number: int | None,
    column_name: str | None,
    value: Any,
    suggestion: str,
) -> None:
    issues.append(
        {
            "Datei": file_name,
            "Tabelle": sheet_name,
            "Prüfung": issue_type,
            "Excel-Zeile": row_number,
            "Spalte": column_name,
            "Wert": value,
            "Vorschlag": suggestion,
        }
    )


def check_sheet(file_path: Path, sheet_name: str) -> list[dict[str, Any]]:
    header_row = find_header_row(file_path, sheet_name)
    data = read_data(file_path, sheet_name)
    issues: list[dict[str, Any]] = []
    required = REQUIRED_COLUMNS.get(sheet_name, set())

    # Pflichtfelder: explizite Konfiguration oder leere Zellen in allen Spalten.
    columns_to_check = required or set(data.columns)
    for column in columns_to_check:
        if column not in data.columns:
            add_issue(
                issues, file_path.name, sheet_name, "Fehlende Spalte", None, column,
                None, "Spaltennamen prüfen oder REQUIRED_COLUMNS anpassen.",
            )
            continue
        for index, value in data[column].items():
            if pd.isna(value) or (isinstance(value, str) and not value.strip()):
                add_issue(
                    issues, file_path.name, sheet_name, "Fehlender Wert",
                    int(index) + header_row + 2,
                    column, value, "Wert ergänzen oder als optional dokumentieren.",
                )

    for column in data.columns:
        series = data[column].dropna()
        if series.empty:
            continue

        # Leerzeichen am Anfang/Ende und uneinheitliche Schreibweise.
        if series.map(lambda value: isinstance(value, str)).any():
            normalized = series.map(normalize_text)
            for key, group in series.groupby(normalized):
                variants = sorted({str(value) for value in group})
                if key and len(variants) > 1:
                    add_issue(
                        issues, file_path.name, sheet_name, "Schreibvariante",
                        None, column, " | ".join(variants),
                        f"Auf eine Schreibweise vereinheitlichen, z. B. '{variants[0]}'.",
                    )

            for index, value in series.items():
                if isinstance(value, str) and value != value.strip():
                    add_issue(
                        issues, file_path.name, sheet_name, "Überflüssige Leerzeichen",
                        int(index) + header_row + 2,
                        column, value, "Leerzeichen am Anfang/Ende entfernen.",
                    )

        # Eindeutigkeit typischer Schlüssel prüfen.
        column_lower = column.casefold()
        looks_like_key = (
            column_lower in {
                "id",
                "code",
                "sku",
                "productcode",
                "stockkeepingunit",
                "hs_object_id",
            }
            or "materialnummer" in column_lower
        )
        if looks_like_key:
            duplicates = series.index[series.duplicated(keep=False)]
            for index in duplicates:
                add_issue(
                    issues, file_path.name, sheet_name, "Doppelter Schlüssel",
                    int(index) + header_row + 2,
                    column, data.at[index, column],
                    "Schlüssel muss eindeutig sein; Dublette prüfen.",
                )

        # Datumsfelder auf nicht parsebare Werte prüfen.
        if "date" in column_lower or "datum" in column_lower or "created" in column_lower:
            parsed = pd.to_datetime(series, format="mixed", errors="coerce")
            for index in series.index[parsed.isna()]:
                add_issue(
                    issues, file_path.name, sheet_name, "Ungültiges Datum",
                    int(index) + header_row + 2,
                    column, data.at[index, column], "Datum im Format YYYY-MM-DD speichern.",
                )

        allowed = ALLOWED_VALUES.get(column)
        if allowed:
            allowed_normalized = {normalize_text(value) for value in allowed}
            for index, value in series.items():
                if normalize_text(value) not in allowed_normalized:
                    add_issue(
                        issues, file_path.name, sheet_name, "Unbekannter Wert",
                        int(index) + header_row + 2,
                        column, value,
                        f"Erlaubte Werte prüfen: {', '.join(sorted(allowed))}.",
                    )

    return issues


def main() -> None:
    issues: list[dict[str, Any]] = []
    input_files = sorted(
        file_path
        for file_path in ROOT.glob("*.xlsx")
        if file_path.name != OUTPUT_FILE.name and not file_path.name.startswith("~$")
    )

    if not input_files:
        raise FileNotFoundError(f"Keine Excel-Datei in {ROOT} gefunden.")

    for file_path in input_files:
        excel_file = pd.ExcelFile(file_path)
        for sheet_name in excel_file.sheet_names:
            if sheet_name not in IGNORED_SHEETS:
                issues.extend(check_sheet(file_path, sheet_name))

    result = pd.DataFrame(issues)
    if result.empty:
        result = pd.DataFrame(
            [{"Ergebnis": "Keine Auffälligkeiten nach den konfigurierten Prüfungen gefunden."}]
        )

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="Auffälligkeiten", index=False)
        pd.DataFrame(
            [
                {"Prüfung": "Fehlende Werte", "Bedeutung": "Zelle ist leer oder enthält nur Leerzeichen."},
                {"Prüfung": "Schreibvariante", "Bedeutung": "Werte unterscheiden sich nur bei Groß-/Kleinschreibung oder Leerzeichen."},
                {"Prüfung": "Doppelter Schlüssel", "Bedeutung": "Typische ID-/Code-Spalte enthält denselben Wert mehrfach."},
                {"Prüfung": "Ungültiges Datum", "Bedeutung": "Wert konnte nicht als Datum gelesen werden."},
                {"Prüfung": "Unbekannter Wert", "Bedeutung": "Wert steht nicht in ALLOWED_VALUES."},
            ]
        ).to_excel(writer, sheet_name="Legende", index=False)

    print(f"Prüfung abgeschlossen: {len(issues)} Auffälligkeiten")
    print(f"Bericht: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
