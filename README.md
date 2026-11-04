# Hackathon_MDM
Hackathon Projekt zu Data Quality

## Start

1. Einmal `install_datencheck.bat` ausführen.
   Das legt die Python-Umgebung an und erzeugt die Standalone-Datenbank
   `data/datencheck.db` inkl. Fehler-Tabellen, SAP/Salesforce/HubSpot-Grundtabellen
   und dokumentierter Beziehungen (`Beziehung`).
   Erneutes Ausführen ist sicher (Schema wird nur bei Bedarf angelegt).
   Bei Schema-Upgrade ggf. alte `data/datencheck.db` löschen und Install erneut laufen lassen.
2. Danach immer `start_datencheck.bat` verwenden. Der Start verwendet
   automatisch `.venv\Scripts\python.exe` und damit die installierten Pakete.

Der direkte Datencheck ist alternativ mit folgendem Befehl möglich:

```powershell
.venv\Scripts\python.exe datencheck_neu.py
```

Nur die Datenbank neu initialisieren / befüllen:

```powershell
.venv\Scripts\python.exe init_db.py
.venv\Scripts\python.exe load_data.py
```
