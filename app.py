"""AgroTechNova Datencheck – Standalone-Webanwendung.

Frontend (Flask) + Prüfengine + SQLite (data/datencheck.db) in einem Prozess.
Der Browser sieht nie die Datenbank selbst, sondern nur gerenderte Seiten.

Start:
    install_datencheck.bat   # einmalig
    start_datencheck.bat     # -> http://127.0.0.1:5000
"""

from __future__ import annotations

import csv
import sqlite3
import threading
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from datencheck_output_sqlite import OUTPUT_FILE, run_check
from init_db import DB_PATH, init_database

ROOT = Path(__file__).resolve().parent
KLASSIFIZIERUNG_CSV = ROOT / "FEHLERKLASSIFIZIERUNG.csv"
HOST = "127.0.0.1"
PORT = 5000

app = Flask(__name__)
app.config["SECRET_KEY"] = "datencheck-lokal"  # nur für Flash-Meldungen
app.config["DATABASE"] = DB_PATH

# Hintergrund-Status für den Datencheck (eine Prüfung gleichzeitig)
_check_lock = threading.Lock()
_check_state: dict = {
    "status": "idle",  # idle | running | done | error
    "running": False,
    "percent": 0.0,
    "message": "",
    "table": "",
    "error": None,
    "output": None,
    "befunde": 0,
    "last_ok": None,
    "last_message": None,
}


# ---------------------------------------------------------------------------
# Stammdaten der Oberfläche
# ---------------------------------------------------------------------------

# Owner-Katalog laut OWNER_VORSCHLAG.md (Code -> Anzeigename)
ABTEILUNGEN = {
    "MDM": "Stammdaten / MDM",
    "PRODUKT": "Produktmanagement",
    "DISPO": "Disposition / Supply",
    "LOGISTIK": "Logistik & Zoll",
    "VERTRIEB": "Vertrieb",
    "MARKETING": "Marketing / Katalog",
    "SERVICE": "Field Service",
    "CUSTOMER": "Customer Success / Kundenstamm",
}

# Schweregrade exakt wie in FEHLERKLASSIFIZIERUNG.csv (Spalte "Schwere"),
# von schwer nach leicht. Schlüssel = CSS-Klasse (sev-…), Anzeige = CSV-Wert.
SCHWEREGRADE = {
    "hoch": "hoch",
    "mittel-hoch": "mittel–hoch",
    "mittel": "mittel",
    "niedrig-mittel": "niedrig–mittel",
    "niedrig": "niedrig",
}


def stufe_von(schwere: str | None) -> str:
    """Schwere aus der DB -> Schlüssel aus SCHWEREGRADE.

    Gedankenstrich/Leerzeichen/Großschreibung werden vereinheitlicht,
    "Mittel - Hoch" == "mittel–hoch". Unbekannte Werte -> "unbekannt".
    """
    wert = (schwere or "").strip().lower().replace("–", "-").replace("—", "-").replace(" ", "")
    return wert if wert in SCHWEREGRADE else "unbekannt"

STATUS_WERTE = ["offen", "in Bearbeitung", "behoben"]

# Salesforce-Objekte, die zur Service-Seite gehören (alles andere -> Sales)
SERVICE_TABELLEN = {"account", "contact", "asset", "workorder"}
SERVICE_CODES = ("SF-A", "SF-C", "SF-S", "SF-W", "SF-H02", "SF-H03")

# Die vier Bereiche / Unterseiten. Zeilen- und Tabellenzahl beschreiben die
# Quelltabellen. Sie werden beim Start aus der DB aktualisiert und liegen in
# `meta` (key='zeilen_sap' usw.).
BEREICHE = {
    "sap": {
        "titel": "SAP Materialstamm",
        "seitentitel": "Fehlerhafte Daten SAP",
        "ueberschrift": "SAP Fehlerliste",
        "tabellen_text": "MARA, Produkte (FERT), Ersatzteile (ERSA)",
        "tabellen": 3,
        "zeilen": 2220,
        "db_tabellen": ["MARA", "Produkte_FERT", "Ersatzteile_ERSA"],
    },
    "salesforce_sales": {
        "titel": "Salesforce Sales",
        "seitentitel": "Fehlerhafte Daten Salesforce_Sales",
        "ueberschrift": "Salesforce_Sales Fehlerliste",
        "tabellen_text": "Product2, Pricebook2, PricebookEntry",
        "tabellen": 3,
        "zeilen": 311,
        "db_tabellen": ["Product2", "Pricebook2", "PricebookEntry"],
    },
    "hubspot": {
        "titel": "HubSpot Produktdaten",
        "seitentitel": "Fehlerhafte Daten HubSpot",
        "ueberschrift": "Hubspot Fehlerliste",
        "tabellen_text": "Products, Price Books, Price Book Items",
        "tabellen": 3,
        "zeilen": 310,
        "db_tabellen": ["Products", "Price_Books", "Price_Book_Items"],
    },
    "salesforce_service": {
        "titel": "Salesforce Service",
        "seitentitel": "Fehlerhafte Daten Salesforce_Service",
        "ueberschrift": "Salesforce_Service Fehlerliste",
        "tabellen_text": "Account, Contact, Asset, WorkOrder",
        "tabellen": 4,
        "zeilen": 733,
        "db_tabellen": ["Account", "Contact", "Asset", "WorkOrder"],
    },
}

# Ergänzungstabelle für den "Datensatz bearbeiten"-Button. Die Tabellen aus
# schema.sql bleiben unverändert; Bearbeitungen landen hier, verknüpft über
# die Fehlerid.
APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS Fehlerbearbeitung (
    Fehlerid       INTEGER PRIMARY KEY,
    Feld           TEXT,
    Ist_Wert       TEXT,
    Korrektur_Wert TEXT,
    Status         TEXT NOT NULL DEFAULT 'offen',
    Kommentar      TEXT,
    Bearbeitet_am  TEXT,
    FOREIGN KEY (Fehlerid) REFERENCES Fehlerliste (Fehlerid) ON DELETE CASCADE
);
"""


# ---------------------------------------------------------------------------
# Datenbank
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def lade_klassifizierung() -> list[dict]:
    if not KLASSIFIZIERUNG_CSV.exists():
        return []
    with KLASSIFIZIERUNG_CSV.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def importiere_fehlerdefinitionen(connection: sqlite3.Connection) -> int:
    """Überträgt FEHLERKLASSIFIZIERUNG.csv in die Tabelle Fehlerdefinition.

    Vorhandene Fehlercodes werden aktualisiert, neue angelegt.
    """
    anzahl = 0
    for zeile in lade_klassifizierung():
        code = (zeile.get("ID") or "").strip()
        if not code:
            continue
        connection.execute(
            """
            INSERT INTO Fehlerdefinition (Fehlercode, Schwere, Owner, Kurzbeschreibung, System)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (Fehlercode) DO UPDATE SET
                Schwere = excluded.Schwere,
                Owner = excluded.Owner,
                Kurzbeschreibung = excluded.Kurzbeschreibung,
                System = excluded.System
            """,
            (
                code,
                (zeile.get("Schwere") or "").strip(),
                (zeile.get("Owner") or "").strip(),
                (zeile.get("Befund") or "").strip(),
                (zeile.get("SYSTEM") or "").strip(),
            ),
        )
        anzahl += 1
    connection.commit()
    return anzahl


def aktualisiere_meta_zaehler(connection: sqlite3.Connection) -> None:
    """Schreibt Ist-Zeilen-/Tabellenzahlen der Quellsysteme in meta."""
    for key, cfg in BEREICHE.items():
        tabellen = cfg["db_tabellen"]
        vorhanden = []
        zeilen = 0
        for name in tabellen:
            try:
                zeilen += connection.execute(
                    f'SELECT COUNT(*) FROM "{name}"'
                ).fetchone()[0]
                vorhanden.append(name)
            except sqlite3.Error:
                continue
        connection.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (f"zeilen_{key}", str(zeilen if vorhanden else cfg["zeilen"])),
        )
        connection.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (f"tabellen_{key}", str(len(vorhanden) if vorhanden else cfg["tabellen"])),
        )
    connection.commit()


def datenbank_vorbereiten() -> None:
    """Legt die DB an (falls nötig) und aktualisiert Fehlerdefinitionen (Upsert)."""
    db_path = Path(app.config["DATABASE"])
    if not db_path.exists():
        init_database(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(APP_SCHEMA)
        # Bei jedem Start: neue Katalogcodes (z. B. *-G0x) ohne Neuinstallation
        importiere_fehlerdefinitionen(connection)
        aktualisiere_meta_zaehler(connection)


# Felder je Fehlercode (Spalte "Felder" der Klassifizierung) als Vorgabe
FELDER_JE_CODE = {
    (z.get("ID") or "").strip(): (z.get("Felder") or "").strip()
    for z in lade_klassifizierung()
}


def meta_wert(key: str, standard):
    row = get_db().execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    if row is None:
        return standard
    try:
        return type(standard)(row["value"])
    except (TypeError, ValueError):
        return standard


# ---------------------------------------------------------------------------
# Fehler laden und zuordnen
# ---------------------------------------------------------------------------

def bereich_von(fehlercode: str, system: str | None, tabelle: str) -> str | None:
    system = (system or "").strip().lower()
    code = (fehlercode or "").upper()
    if not system:
        if code.startswith("SAP-"):
            system = "sap"
        elif code.startswith("HS-"):
            system = "hubspot"
        elif code.startswith("SF-"):
            system = "salesforce"
    if system == "sap":
        return "sap"
    if system == "hubspot":
        return "hubspot"
    if system == "salesforce":
        tab = (tabelle or "").strip().lower()
        if tab in SERVICE_TABELLEN or code.startswith(SERVICE_CODES):
            return "salesforce_service"
        return "salesforce_sales"
    return None


def lade_fehler() -> list[dict]:
    rows = get_db().execute(
        """
        SELECT l.Fehlerid, l.Fehlercode, l.Ursprungstabelle, l.Ursprungs_ID,
               d.Schwere, d.Owner, d.Kurzbeschreibung, d.System,
               b.Feld, b.Ist_Wert, b.Korrektur_Wert, b.Status, b.Kommentar,
               b.Bearbeitet_am
        FROM Fehlerliste AS l
        LEFT JOIN Fehlerdefinition AS d ON d.Fehlercode = l.Fehlercode
        LEFT JOIN Fehlerbearbeitung AS b ON b.Fehlerid = l.Fehlerid
        ORDER BY l.Ursprungstabelle, l.Ursprungs_ID, l.Fehlercode
        """
    ).fetchall()

    fehler = []
    for r in rows:
        f = dict(r)
        f["bereich"] = bereich_von(f["Fehlercode"], f["System"], f["Ursprungstabelle"])
        f["stufe"] = stufe_von(f["Schwere"])
        f["stufe_anzeige"] = SCHWEREGRADE.get(f["stufe"], f["Schwere"] or "–")
        f["Status"] = f["Status"] or "offen"
        f["Feld_anzeige"] = f["Feld"] or FELDER_JE_CODE.get(f["Fehlercode"], "")
        f["Owner_name"] = ABTEILUNGEN.get(f["Owner"] or "", f["Owner"] or "–")
        fehler.append(f)
    return fehler


def ist_offen(f: dict) -> bool:
    return f["Status"] != "behoben"


# ---------------------------------------------------------------------------
# Seiten
# ---------------------------------------------------------------------------

@app.route("/")
@app.route("/index.html")
def index():
    with _check_lock:
        check_running = _check_state["running"]
        last_ok = _check_state["last_ok"]
        last_message = _check_state["last_message"]
        if last_message and not check_running:
            flash(last_message, "ok" if last_ok else "fehler")
            _check_state["last_message"] = None
            _check_state["last_ok"] = None

    alle = lade_fehler()
    offen = [f for f in alle if ist_offen(f)]

    gesamt_zeilen = 0
    karten = []
    for key, cfg in BEREICHE.items():
        zeilen = meta_wert(f"zeilen_{key}", cfg["zeilen"])
        tabellen = meta_wert(f"tabellen_{key}", cfg["tabellen"])
        gesamt_zeilen += zeilen
        karten.append({
            "key": key,
            "titel": cfg["titel"],
            "meta": f'{cfg["tabellen_text"]} · {de_zahl(zeilen)} Zeilen',
            "tabellen": tabellen,
            "fehler": sum(1 for f in offen if f["bereich"] == key),
        })

    betroffene = len({(f["Ursprungstabelle"], f["Ursprungs_ID"]) for f in offen})
    clean_rate = (gesamt_zeilen - betroffene) / gesamt_zeilen * 100 if gesamt_zeilen else 100.0

    anzahl = {key: 0 for key in SCHWEREGRADE}
    anzahl["unbekannt"] = 0
    for f in offen:
        anzahl[f["stufe"]] += 1
    summe = sum(anzahl.values())
    stufen = [
        {
            "key": key,
            "name": SCHWEREGRADE.get(key, "ohne Schwere"),
            "anzahl": n,
            "anteil": n / summe * 100 if summe else 0,
        }
        for key, n in anzahl.items()
        if key != "unbekannt" or n  # "ohne Schwere" nur zeigen, wenn es vorkommt
    ]

    return render_template(
        "index.html",
        gesamt_fehler=len(offen),
        betroffene=betroffene,
        gesamt_zeilen=gesamt_zeilen,
        clean_rate=clean_rate,
        stufen=stufen,
        anzahl_hoch=anzahl["hoch"],
        karten=karten,
        check_running=check_running,
    )


@app.route("/bereich/<bereich>")
def fehlerliste(bereich: str):
    if bereich not in BEREICHE:
        abort(404)
    cfg = BEREICHE[bereich]
    abteilung = request.args.get("abteilung", "").strip()

    im_bereich = [f for f in lade_fehler() if f["bereich"] == bereich]

    # Abteilungen für den Filter: Katalog + alle, die in den Daten vorkommen
    zaehler: dict[str, int] = {}
    for f in im_bereich:
        if ist_offen(f):
            zaehler[f["Owner"] or ""] = zaehler.get(f["Owner"] or "", 0) + 1
    codes = list(ABTEILUNGEN) + sorted(c for c in zaehler if c and c not in ABTEILUNGEN)
    abteilungen = [
        {"code": c, "name": ABTEILUNGEN.get(c, c), "anzahl": zaehler.get(c, 0)}
        for c in codes
    ]

    eintraege = [f for f in im_bereich if not abteilung or f["Owner"] == abteilung]
    # offene zuerst, behobene ans Ende
    eintraege.sort(key=lambda f: f["Status"] == "behoben")

    # Fehlercodes dieses Bereichs für das Bearbeiten-Formular
    system = {"sap": "sap", "hubspot": "hubspot"}.get(bereich, "salesforce")
    definitionen = [
        dict(r) for r in get_db().execute(
            "SELECT Fehlercode, Kurzbeschreibung FROM Fehlerdefinition "
            "WHERE lower(System) = ? ORDER BY Fehlercode",
            (system,),
        )
    ]

    return render_template(
        "fehlerliste.html",
        bereich=bereich,
        cfg=cfg,
        eintraege=eintraege,
        offene_anzahl=sum(1 for f in eintraege if ist_offen(f)),
        abteilungen=abteilungen,
        abteilung=abteilung,
        definitionen=definitionen,
        status_werte=STATUS_WERTE,
    )


# Alte Dateinamen weiterhin erreichbar machen (Links/Lesezeichen)
ALTE_DATEINAMEN = {
    "fehlerhafte Daten SAP.html": "sap",
    "fehlerhafte Daten Salesforce_Sales.html": "salesforce_sales",
    "fehlerhafte Daten Hubspot.html": "hubspot",
    "fehlerhafte Daten Salesforce_Service.html": "salesforce_service",
}


@app.route("/<path:dateiname>")
def alte_seite(dateiname: str):
    if dateiname in ALTE_DATEINAMEN:
        return redirect(url_for("fehlerliste", bereich=ALTE_DATEINAMEN[dateiname]))
    abort(404)


def _check_snapshot() -> dict:
    with _check_lock:
        return {
            "status": _check_state["status"],
            "running": _check_state["running"],
            "percent": _check_state["percent"],
            "message": _check_state["message"],
            "table": _check_state["table"],
            "error": _check_state["error"],
            "output": _check_state["output"],
            "befunde": _check_state["befunde"],
        }


def _datencheck_job(db_path: Path) -> None:
    def on_progress(info) -> None:
        with _check_lock:
            _check_state["status"] = str(info.get("status") or "running")
            _check_state["percent"] = float(info.get("percent") or 0)
            _check_state["message"] = str(info.get("message") or "")
            _check_state["table"] = str(info.get("table") or "")

    try:
        output = run_check(
            db_path=db_path,
            output_file=OUTPUT_FILE,
            on_progress=on_progress,
        )
        with sqlite3.connect(db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            anzahl = connection.execute("SELECT COUNT(*) FROM Fehlerliste").fetchone()[0]
            aktualisiere_meta_zaehler(connection)
        message = (
            f"Datencheck abgeschlossen: {anzahl} Befunde in der Fehlerliste. "
            f"Excel-Bericht: {output.name}"
        )
        with _check_lock:
            _check_state["status"] = "done"
            _check_state["percent"] = 100.0
            _check_state["message"] = message
            _check_state["table"] = ""
            _check_state["error"] = None
            _check_state["output"] = str(output)
            _check_state["befunde"] = int(anzahl)
            _check_state["last_ok"] = True
            _check_state["last_message"] = message
    except Exception as error:
        with _check_lock:
            _check_state["status"] = "error"
            _check_state["percent"] = 0.0
            _check_state["message"] = str(error)
            _check_state["error"] = str(error)
            _check_state["last_ok"] = False
            _check_state["last_message"] = f"Datencheck fehlgeschlagen: {error}"
    finally:
        with _check_lock:
            _check_state["running"] = False


@app.get("/datencheck/status")
def datencheck_status():
    return jsonify(_check_snapshot())


@app.post("/datencheck/starten")
def datencheck_starten():
    """Startet den klassifizierten Datencheck im Hintergrund."""
    wants_json = (
        "application/json" in (request.headers.get("Accept") or "")
        or request.headers.get("X-Requested-With") == "fetch"
    )
    db_path = Path(app.config["DATABASE"])
    with _check_lock:
        if _check_state["running"]:
            if wants_json:
                return jsonify(_check_snapshot()), 409
            flash("Datencheck läuft bereits – bitte warten.", "fehler")
            return redirect(url_for("index"))
        _check_state.update(
            status="running",
            running=True,
            percent=0.0,
            message="Starte Datencheck …",
            table="",
            error=None,
            output=None,
            befunde=0,
            last_ok=None,
            last_message=None,
        )
    threading.Thread(target=_datencheck_job, args=(db_path,), daemon=True).start()
    if wants_json:
        return jsonify(_check_snapshot())
    flash(
        "Datencheck gestartet. Fortschritt erscheint auf der Startseite.",
        "ok",
    )
    return redirect(url_for("index"))


@app.post("/fehler/<int:fehlerid>/bearbeiten")
def fehler_bearbeiten(fehlerid: int):
    db = get_db()
    vorhanden = db.execute(
        "SELECT Fehlerid FROM Fehlerliste WHERE Fehlerid = ?", (fehlerid,)
    ).fetchone()
    if vorhanden is None:
        abort(404)

    form = request.form
    fehlercode = form.get("Fehlercode", "").strip()
    tabelle = form.get("Ursprungstabelle", "").strip()
    ursprungs_id = form.get("Ursprungs_ID", "").strip()
    status = form.get("Status", "offen").strip()

    def leer_zu_none(name: str):
        wert = form.get(name, "").strip()
        return wert or None

    fehler = []
    if not tabelle or not ursprungs_id:
        fehler.append("Tabelle und Materialnummer/ID dürfen nicht leer sein.")
    if status not in STATUS_WERTE:
        fehler.append("Ungültiger Status.")
    if db.execute(
        "SELECT 1 FROM Fehlerdefinition WHERE Fehlercode = ?", (fehlercode,)
    ).fetchone() is None:
        fehler.append(f"Unbekannter Fehlercode: {fehlercode or '–'}")

    if fehler:
        for text in fehler:
            flash(text, "fehler")
    else:
        jetzt = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        db.execute(
            "UPDATE Fehlerliste SET Fehlercode = ?, Ursprungstabelle = ?, Ursprungs_ID = ? "
            "WHERE Fehlerid = ?",
            (fehlercode, tabelle, ursprungs_id, fehlerid),
        )
        db.execute(
            """
            INSERT INTO Fehlerbearbeitung
                (Fehlerid, Feld, Ist_Wert, Korrektur_Wert, Status, Kommentar, Bearbeitet_am)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (Fehlerid) DO UPDATE SET
                Feld = excluded.Feld,
                Ist_Wert = excluded.Ist_Wert,
                Korrektur_Wert = excluded.Korrektur_Wert,
                Status = excluded.Status,
                Kommentar = excluded.Kommentar,
                Bearbeitet_am = excluded.Bearbeitet_am
            """,
            (
                fehlerid,
                leer_zu_none("Feld"),
                leer_zu_none("Ist_Wert"),
                leer_zu_none("Korrektur_Wert"),
                status,
                leer_zu_none("Kommentar"),
                jetzt,
            ),
        )
        db.commit()
        flash(f"Datensatz {ursprungs_id} gespeichert.", "ok")

    ziel = form.get("next", "")
    if not ziel.startswith("/") or ziel.startswith("//"):
        ziel = url_for("index")
    return redirect(ziel)


@app.template_filter("de_zahl")
def de_zahl(wert, nachkomma: int = 0) -> str:
    text = f"{wert:,.{nachkomma}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


datenbank_vorbereiten()


def _browser_oeffnen() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}/")


if __name__ == "__main__":
    threading.Timer(0.8, _browser_oeffnen).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
