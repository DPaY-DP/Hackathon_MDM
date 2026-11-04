# AgroTechNova Datencheck

Lokales Datenqualitäts-Tool für AgroTechNova. Es prüft Stammdaten aus **SAP**, **Salesforce** und **HubSpot**, bewertet Befunde nach Schwere und Zuständigkeit und liefert eine nachvollziehbare Befundliste für Fachbereiche und Geschäftsführung.

Entstanden im Hackathon **Mission Datenvertrauen**.

## Was das Tool leistet

| Briefing-Anforderung | Umsetzung |
|---|---|
| Probleme finden | Prüfungen innerhalb der Dateien und über Systemgrenzen hinweg |
| Probleme bewerten | Schweregrad, Fehlerklasse, Ursache/Ebene, Impact |
| Weg zur Besserung | Korrekturvorschlag + klarer Owner je Befund |
| Fachlich nutzbar | Web-App – Datencheck starten, Bereiche öffnen, Datensätze bearbeiten |
| On-Prem / lokal | Läuft vollständig auf dem lokalen Rechner, Daten bleiben im Haus |

## Voraussetzungen

- Windows
- Python 3.10+ (`py`-Launcher)
- Die Excel-Exporte unter `Datenquellen/Dirty_Extended/` (werden bei der Installation geladen)

## Installation (einmalig)

Im Projektordner doppelklicken bzw. ausführen:

```bat
install_datencheck.bat
```

Damit wird:

1. die virtuelle Umgebung `.venv` angelegt
2. Abhängigkeiten aus `requirements.txt` installiert (`flask`, `pandas`, `openpyxl`)
3. die lokale SQLite-Datenbank `data/datencheck.db` aus `schema.sql` initialisiert und befüllt

Erneutes Ausführen ist sicher. Bei Schema-Upgrade ggf. `data/datencheck.db` löschen und die Installation erneut starten.

## Start (Standalone)

```bat
start_datencheck.bat
```

Das öffnet die Web-Oberfläche unter [http://127.0.0.1:5000](http://127.0.0.1:5000).

1. **Datencheck starten** klicken
2. KPIs und Bereichskarten aktualisieren sich aus `Fehlerliste`
3. In einem Bereich Datensätze öffnen, filtern und bearbeiten
4. Optionaler Excel-Bericht: `datencheck_output_sqlite_01.xlsx`

Zum Beenden das Konsolenfenster schließen.

## Architektur

```
app.py                         # Frontend (Flask) + Einstieg
datencheck_output_sqlite.py    # Prüf-/Klassifizierungslogik
schema.sql + init_db.py        # Datenbankschema
load_data.py                   # Excel → SQLite
data/datencheck.db             # lokale Standalone-DB
templates/ + static/           # Oberfläche
```

Ablauf: Excel-Quellen → SQLite → Datencheck schreibt `Fehlerliste` (+ `Fehlerbearbeitung`) → Flask zeigt Dashboard.

## Ergebnis / Befundliste

| Spalte / Feld | Bedeutung |
|---|---|
| Tabelle / Ursprung | Quelltabelle in der DB |
| Materialnummer / ID | betroffener Datensatz |
| Feld / Ist-Wert | betroffenes Feld und aktueller Wert |
| Fehlerbeschreibung | Befund aus dem Katalog |
| Schwere | hoch … niedrig |
| Owner | wer die Korrektur zuerst anpackt |
| Status | offen / in Bearbeitung / behoben |

Katalog: `FEHLERKLASSIFIZIERUNG.csv` → Tabelle `Fehlerdefinition`. Regeln: `datencheck_regeln.json`.

## Hinweise

- Führendes System für Materialstammdaten: **SAP**. CRM- und Katalogdaten werden dagegen abgeglichen.
- Regeln und Zuständigkeiten können ohne Codeänderung in `datencheck_regeln.json` und `FEHLERKLASSIFIZIERUNG.csv` angepasst werden.
- Alternativen ohne Web-UI: `datencheck_output_sqlite.py` (CLI) bzw. `datencheck_output_sqlite_app.py` (Tkinter).
