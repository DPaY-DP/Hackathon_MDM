@echo off
setlocal
py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
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
echo Installation abgeschlossen. Datenbank: data\datencheck.db
echo Start mit: .venv\Scripts\python.exe datencheck_app.py
pause
