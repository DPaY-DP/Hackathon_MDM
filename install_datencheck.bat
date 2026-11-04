@echo off
setlocal
py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Installation abgeschlossen.
echo Start mit: .venv\Scripts\python.exe datencheck_app.py
pause
