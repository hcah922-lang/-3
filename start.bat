@echo off
title Dating Bot
cd /d "%~dp0"
if not exist bot.py (
  echo [x] bot.py not found
  pause
  exit /b 1
)
if not exist .env (
  echo [x] No .env file. Copy .env.example to .env and fill it.
  pause
  exit /b 1
)
python --version
if errorlevel 1 (
  echo [x] Python not found in PATH. Install Python 3.12 with Add to PATH.
  pause
  exit /b 1
)
if not exist venv\Scripts\activate.bat (
  echo [i] Creating venv...
  python -m venv venv
  if errorlevel 1 (
    echo [x] venv failed
    pause
    exit /b 1
  )
  call venv\Scripts\activate.bat
  echo [i] Installing deps...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [x] pip install failed
    pause
    exit /b 1
  )
) else (
  call venv\Scripts\activate.bat
)
echo [i] Starting bot...
python bot.py
echo [i] Stopped, exit code: %errorlevel%
pause
