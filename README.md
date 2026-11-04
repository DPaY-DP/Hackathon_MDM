# AgroTechNova Datencheck

Lokales Datenqualitäts-Tool für AgroTechNova. Es prüft Stammdaten aus **SAP**, **Salesforce** und **HubSpot**, bewertet Befunde nach Schwere und Zuständigkeit und liefert Fachbereichen eine bedienbare Web-Oberfläche inklusive Befundliste.

Entstanden im Hackathon **Mission Datenvertrauen**.

## Was das Tool leistet

| Briefing-Anforderung | Umsetzung |
|---|---|
| Probleme finden | Prüfungen in allen Quelltabellen und über Systemgrenzen hinweg |
| Probleme bewerten | Schweregrad, Fehlerklasse, Ebene, Impact, Owner |
| Zustand sichtbar machen | Dashboard mit KPIs und Bereichskarten (SAP, SF Sales, HubSpot, SF Service) |
| Weg zur Besserung | Korrekturvorschlag, Owner, Status (offen / in Bearbeitung / behoben) |
| Fachlich nutzbar | Web-App im Browser – Check starten, filtern, Datensätze bearbeiten |
| On-Prem / lokal | Läuft auf dem lokalen Rechner; Daten bleiben in `data/datencheck.db` |

## Voraussetzungen

- Windows
- Python 3.10+ (Launcher `py`)
- Excel-Quellen unter `Datenquellen/Dirty_Extended/`:

| Datei | System |
|---|---|
| `AgroTechNova_Stammdaten_MARC_dirty_1.xlsx` | SAP |
| `AgroTechNova_Produktdaten_Salesforce_dirty_1.xlsx` | Salesforce Sales |
| `AgroTechNova_Produktdaten_HubSpot_dirty_1.xlsx` | HubSpot |
| `AgroTechNova_Service_Salesforce_dirty_1.xlsx` | Salesforce Service |

## Installation (einmalig)

Im Projektordner:

```bat
install_datencheck.bat
```

Das Skript:

1. legt die virtuelle Umgebung `.venv` an
2. installiert Abhängigkeiten aus `requirements.txt` (`flask`, `pandas`, `openpyxl`)
3. initialisiert `data/datencheck.db` aus `schema.sql`
4. lädt Katalog (`FEHLERKLASSIFIZIERUNG.csv`) und Excel-Daten ein

Erneutes Ausführen ist sicher. Bei Schema-Upgrade ggf. `data/datencheck.db` löschen und die Installation erneut starten.

## Start

```bat
start_datencheck.bat
```

Öffnet die Web-Oberfläche unter [http://127.0.0.1:5000](http://127.0.0.1:5000).

Zum Beenden das Konsolenfenster schließen.

### Nutzung in der Oberfläche

1. **Datencheck starten** – Prüfung läuft im Hintergrund (Fortschrittsanzeige)
2. KPIs und Bereichskarten aktualisieren sich aus der Tabelle `Fehlerliste`
3. Bereich öffnen (SAP / Salesforce Sales / HubSpot / Salesforce Service)
4. optional nach **Abteilung (Owner)** filtern
5. **Datensatz bearbeiten** – Korrekturwert, Status, Kommentar speichern

Optionaler Excel-Export der Befunde: `datencheck_output_sqlite_01.xlsx`

## Architektur

```
Excel (Dirty_Extended)  →  SQLite (data/datencheck.db)  →  Datencheck  →  Fehlerliste
                                                                         ↓
                                                              Flask-Web-UI (Browser)
```

| Datei / Ordner | Rolle |
|---|---|
| `app.py` | Flask-Frontend + API (Start/Status des Checks, Bearbeitung) |
| `datencheck_output_sqlite.py` | Prüf- und Klassifizierungslogik gegen SQLite |
| `schema.sql` / `init_db.py` | Datenbankschema |
| `load_data.py` | Excel → SQLite |
| `FEHLERKLASSIFIZIERUNG.csv` | Befundkatalog → Tabelle `Fehlerdefinition` |
| `datencheck_regeln.json` | fachlich änderbare Prüfregeln |
| `templates/` + `static/` | Oberfläche |
| `install_datencheck.bat` | Installation |
| `start_datencheck.bat` | Start der Web-App |

## Ergebnis / Befundliste

Primär in der DB (`Fehlerliste` + `Fehlerbearbeitung`), zusätzlich als Excel.

| Feld | Briefing-Bezug |
|---|---|
| Ursprungstabelle / Datei | Quellsystem / Tabelle |
| Ursprungs_ID / Zeile | betroffener Datensatz |
| Feld / Ist-Wert | betroffenes Feld |
| Fehlerbeschreibung / Prüfung | Befund |
| Schwere | hoch … niedrig (inkl. Zwischenstufen) |
| Owner | wer die Korrektur zuerst anpackt |
| Vorschlag | Korrekturhinweis |
| Status | offen / in Bearbeitung / behoben |

## Alternativen ohne Web-UI

```bat
.venv\Scripts\python.exe datencheck_output_sqlite.py
.venv\Scripts\python.exe datencheck_output_sqlite_app.py
```

Im Ordner `output_software/` liegt außerdem ein vorgebauter Standalone (`AgroTechNova_Datencheck_Output.exe`) für den Excel-basierten Check ohne Flask.

## Hinweise

- Führendes System für Materialstammdaten: **SAP**. CRM- und Katalogdaten werden dagegen abgeglichen.
- Regeln und Zuständigkeiten ohne Codeänderung anpassen über `datencheck_regeln.json` und `FEHLERKLASSIFIZIERUNG.csv`.
- Owner-Modell: siehe `OWNER_VORSCHLAG.md` (MDM, PRODUKT, DISPO, LOGISTIK, VERTRIEB, MARKETING, SERVICE, CUSTOMER).
