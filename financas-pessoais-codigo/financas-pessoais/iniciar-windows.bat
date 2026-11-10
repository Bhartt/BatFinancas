@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Instale primeiro conforme README.md: py -3.12 -m venv .venv
  pause
  exit /b 1
)
".venv\Scripts\python.exe" iniciar.py %*
if errorlevel 1 pause
