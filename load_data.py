"""Befüllt die Standalone-DB aus FEHLERKLASSIFIZIERUNG.csv und Datenquellen/Dirty_Extended.

Aufruf:
    python load_data.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from init_db import DB_PATH, get_connection, init_database


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "Datenquellen" / "Dirty_Extended"
CSV_PATH = ROOT / "FEHLERKLASSIFIZIERUNG.csv"

SAP_FILE = DATA_DIR / "AgroTechNova_Stammdaten_MARC_dirty_1.xlsx"
SF_PRODUCT_FILE = DATA_DIR / "AgroTechNova_Produktdaten_Salesforce_dirty_1.xlsx"
SF_SERVICE_FILE = DATA_DIR / "AgroTechNova_Service_Salesforce_dirty_1.xlsx"
HS_FILE = DATA_DIR / "AgroTechNova_Produktdaten_HubSpot_dirty_1.xlsx"

# Reihenfolge: Eltern vor Kindern (für dokumentierte FKs)
TABLE_SOURCES: list[tuple[str, Path, str, list[str]]] = [
    # table, file, sheet, preferred key columns (for cleanup)
    ("MARA", SAP_FILE, "MARA", ["MATNR"]),
    ("Produkte_FERT", SAP_FILE, "Produkte (FERT)", ["MATNR", "WERKS"]),
    ("Ersatzteile_ERSA", SAP_FILE, "Ersatzteile (ERSA)", ["MATNR", "WERKS"]),
    ("Account", SF_SERVICE_FILE, "Account", ["Id"]),
    ("Product2", SF_PRODUCT_FILE, "Product2", ["Id"]),
    ("Pricebook2", SF_PRODUCT_FILE, "Pricebook2", ["Id"]),
    ("Contact", SF_SERVICE_FILE, "Contact", ["Id"]),
    ("Asset", SF_SERVICE_FILE, "Asset", ["Id"]),
    ("WorkOrder", SF_SERVICE_FILE, "WorkOrder", ["Id"]),
    ("PricebookEntry", SF_PRODUCT_FILE, "PricebookEntry", ["Id"]),
    ("Products", HS_FILE, "Products", ["hs_object_id"]),
    ("Price_Books", HS_FILE, "Price Books", ["hs_object_id"]),
    ("Price_Book_Items", HS_FILE, "Price Book Items", ["hs_object_id"]),
]


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
        # Prefer rows that look like real field headers
        joined = " ".join(values).casefold()
        if any(
            token in joined
            for token in ("matnr", "hs_object_id", "productcode", "accountid", "id")
        ):
            score += 10
        if score > best_score:
            best_row, best_score = int(row_number), score
    return best_row


def read_sheet(file_path: Path, sheet_name: str) -> pd.DataFrame:
    header_row = find_header_row(file_path, sheet_name)
    data = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
    data = data.dropna(axis=1, how="all").copy()
    data.columns = [
        str(column).strip()
        if not str(column).startswith("Unnamed:")
        else f"Spalte_{index + 1}"
        for index, column in enumerate(data.columns)
    ]
    # Drop fully empty rows
    data = data.dropna(how="all")
    return data


def cell_to_db(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return int(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    # Normalize numeric IDs that are whole numbers to plain strings without .0
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int,)):
        return str(value)
    text = str(value).strip()
    return text if text != "" else None


def table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def load_fehlerdefinition(connection: sqlite3.Connection) -> int:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV fehlt: {CSV_PATH}")
    frame = pd.read_csv(CSV_PATH, sep=";", encoding="utf-8")
    required = {"SYSTEM", "ID", "Befund", "Schwere", "Owner"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"CSV-Spalten fehlen: {sorted(missing)}")

    connection.execute("DELETE FROM Fehlerliste")
    connection.execute("DELETE FROM Fehlerdefinition")
    rows = []
    for _, row in frame.iterrows():
        rows.append(
            (
                str(row["ID"]).strip(),
                str(row["Schwere"]).strip(),
                str(row["Owner"]).strip(),
                str(row["Befund"]).strip(),
                str(row["SYSTEM"]).strip(),
            )
        )
    connection.executemany(
        """
        INSERT OR REPLACE INTO Fehlerdefinition
            (Fehlercode, Schwere, Owner, Kurzbeschreibung, System)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def prepare_frame(
    connection: sqlite3.Connection,
    table: str,
    data: pd.DataFrame,
    key_columns: list[str],
) -> pd.DataFrame:
    db_cols = table_columns(connection, table)
    usable = [col for col in db_cols if col in data.columns]
    if not usable:
        raise ValueError(f"{table}: keine passenden Spalten in Excel ({list(data.columns)[:8]}...)")

    frame = data[usable].copy()
    for col in usable:
        frame[col] = frame[col].map(cell_to_db)

    # Drop rows without primary key values
    for key in key_columns:
        if key in frame.columns:
            frame = frame[frame[key].notna() & (frame[key].astype(str).str.len() > 0)]

    # Drop duplicate PKs, keep first
    pk_cols = [key for key in key_columns if key in frame.columns]
    if pk_cols:
        frame = frame.drop_duplicates(subset=pk_cols, keep="first")

    return frame


def load_table(
    connection: sqlite3.Connection,
    table: str,
    file_path: Path,
    sheet_name: str,
    key_columns: list[str],
) -> int:
    if not file_path.exists():
        raise FileNotFoundError(f"Excel fehlt: {file_path}")
    data = read_sheet(file_path, sheet_name)
    frame = prepare_frame(connection, table, data, key_columns)
    connection.execute(f"DELETE FROM {table}")
    if frame.empty:
        return 0
    columns = list(frame.columns)
    placeholders = ", ".join("?" for _ in columns)
    col_sql = ", ".join(columns)
    values = [tuple(row) for row in frame.itertuples(index=False, name=None)]
    connection.executemany(
        f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
        values,
    )
    return len(values)


BEREICH_TABELLEN: dict[str, list[str]] = {
    "sap": ["MARA", "Produkte_FERT", "Ersatzteile_ERSA"],
    "salesforce_sales": ["Product2", "Pricebook2", "PricebookEntry"],
    "hubspot": ["Products", "Price_Books", "Price_Book_Items"],
    "salesforce_service": ["Account", "Contact", "Asset", "WorkOrder"],
}


def write_bereich_meta(connection: sqlite3.Connection, counts: dict[str, int]) -> None:
    for key, tables in BEREICH_TABELLEN.items():
        zeilen = sum(counts.get(name, 0) for name in tables)
        connection.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (f"zeilen_{key}", str(zeilen)),
        )
        connection.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (f"tabellen_{key}", str(len(tables))),
        )


def load_all(db_path: Path = DB_PATH) -> dict[str, int]:
    init_database(db_path)
    counts: dict[str, int] = {}
    with get_connection(db_path) as connection:
        # Dirty Data enthält absichtlich kaputte Referenzen
        connection.execute("PRAGMA foreign_keys = OFF")
        counts["Fehlerdefinition"] = load_fehlerdefinition(connection)
        for table, file_path, sheet_name, keys in TABLE_SOURCES:
            counts[table] = load_table(connection, table, file_path, sheet_name, keys)
            print(f"  {table}: {counts[table]} Zeilen")
        write_bereich_meta(connection, counts)
        connection.commit()
    return counts


def main() -> int:
    try:
        print(f"Lade Daten nach {DB_PATH} ...")
        counts = load_all()
    except Exception as error:
        print(f"Datenladung fehlgeschlagen: {error}", file=sys.stderr)
        return 1

    total = sum(counts.values())
    print(f"Fertig: {total} Zeilen in {len(counts)} Tabellen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
