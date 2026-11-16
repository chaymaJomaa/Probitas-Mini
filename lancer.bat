@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
python -m pip install --user flask pypdf python-docx
python app.py
pause
