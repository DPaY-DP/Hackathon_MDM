@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Virtuelle Umgebung fehlt. Bitte zuerst install_datencheck.bat ausfuehren.
  pause
  exit /b 1
)

if not exist "data\datencheck.db" (
  echo Datenbank fehlt. Bitte zuerst install_datencheck.bat ausfuehren.
  pause
  exit /b 1
)

echo Starte AgroTechNova Datencheck ...
echo Browser oeffnet http://127.0.0.1:5000
echo Zum Beenden dieses Fenster schliessen.
echo.
".venv\Scripts\python.exe" app.py
if errorlevel 1 (
  echo.
  echo Start fehlgeschlagen.
  pause
  exit /b 1
)
