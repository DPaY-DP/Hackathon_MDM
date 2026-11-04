@echo off
setlocal
cd /d "%~dp0"

py -m venv .venv
if errorlevel 1 (
  echo Python-Launcher "py" nicht gefunden. Bitte Python 3.10+ installieren.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Abhaengigkeiten konnten nicht installiert werden.
  pause
  exit /b 1
)

python init_db.py
if errorlevel 1 (
  echo Datenbank-Initialisierung fehlgeschlagen.
  pause
  exit /b 1
)

python load_data.py
if errorlevel 1 (
  echo Datenladung fehlgeschlagen.
  pause
  exit /b 1
)

echo.
echo Installation abgeschlossen.
echo Datenbank: data\datencheck.db
echo Start mit: start_datencheck.bat
echo.
pause
