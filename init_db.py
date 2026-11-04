"""Legt die Standalone-SQLite-Datenbank mit leerem Schema an.

Aufruf (nach venv-Aktivierung):
    python init_db.py
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "datencheck.db"
SCHEMA_PATH = ROOT / "schema.sql"
SCHEMA_VERSION = "3"

# Offizielle Power-BI-/Power-Pivot-Beziehungen (Manage Relationships)
# Format: VonTabelle, VonSpalte, NachTabelle, NachSpalte, Art, Systemkontext
# Art: FK = in SQLite erzwungen, PowerBI = wie im Modell, ohne harte FK (Dirty Data)
BEZIEHUNGEN: list[tuple[str, str, str, str, str, str]] = [
    ("Asset", "AccountId", "Account", "Id", "FK", "Salesforce"),
    ("Asset", "ContactId", "Contact", "Id", "FK", "Salesforce"),
    ("Asset", "Product2Id", "Product2", "Id", "FK", "Salesforce"),
    ("Ersatzteile_ERSA", "MATNR", "MARA", "MATNR", "FK", "SAP"),
    ("Price_Book_Items", "hs_sku", "Products", "hs_sku", "PowerBI", "HubSpot"),
    ("Price_Book_Items", "price_book_id", "Price_Books", "hs_object_id", "FK", "HubSpot"),
    ("PricebookEntry", "Product2Id", "Product2", "Id", "FK", "Salesforce"),
    ("PricebookEntry", "Pricebook2Id", "Pricebook2", "Id", "FK", "Salesforce"),
    ("Product2", "ATN_SAP_Materialnummer__c", "MARA", "MATNR", "PowerBI", "Salesforce->SAP"),
    ("Products", "atn_sap_materialnummer", "MARA", "MATNR", "PowerBI", "HubSpot->SAP"),
    ("Produkte_FERT", "MATNR", "MARA", "MATNR", "FK", "SAP"),
    ("WorkOrder", "AssetId", "Asset", "Id", "FK", "Salesforce"),
    # DQ-Modell (nicht aus Power BI)
    ("Fehlerliste", "Fehlercode", "Fehlerdefinition", "Fehlercode", "FK", "DQ"),
]


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def seed_beziehungen(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM Beziehung")
    connection.executemany(
        """
        INSERT INTO Beziehung (
            VonTabelle, VonSpalte, NachTabelle, NachSpalte, Art, Systemkontext
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        BEZIEHUNGEN,
    )


def init_database(
    db_path: Path = DB_PATH,
    schema_path: Path = SCHEMA_PATH,
) -> Path:
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema-Datei fehlt: {schema_path}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    schema_sql = schema_path.read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    with get_connection(db_path) as connection:
        connection.executescript(schema_sql)
        seed_beziehungen(connection)
        connection.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
        connection.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("updated_at", now),
        )
        existing = connection.execute(
            "SELECT value FROM meta WHERE key = ?",
            ("created_at",),
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                ("created_at", now),
            )
        connection.commit()

    return db_path


def main() -> int:
    try:
        db_path = init_database()
    except Exception as error:
        print(f"Datenbank-Initialisierung fehlgeschlagen: {error}", file=sys.stderr)
        return 1

    print(f"Datenbank bereit: {db_path}")
    print(f"Schema-Version: {SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
