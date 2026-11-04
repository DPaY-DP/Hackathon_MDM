# Hackathon_MDM
Hackathon Projekt zu Data Quality

## Start

1. Einmal `install_datencheck.bat` ausführen.
   Das legt die Python-Umgebung an und erzeugt die Standalone-Datenbank
   `data/datencheck.db` (Tabellen `Fehlerdefinition`, `Fehlerliste`).
   Erneutes Ausführen ist sicher (Schema wird nur bei Bedarf angelegt).
2. Danach immer `start_datencheck.bat` verwenden. Der Start verwendet
   automatisch `.venv\Scripts\python.exe` und damit die installierten Pakete.

Der direkte Datencheck ist alternativ mit folgendem Befehl möglich:

```powershell
.venv\Scripts\python.exe datencheck_neu.py
```

Nur die Datenbank neu initialisieren:

```powershell
.venv\Scripts\python.exe init_db.py
```
