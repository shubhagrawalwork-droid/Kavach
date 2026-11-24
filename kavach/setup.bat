@echo off
cd /d "%~dp0"
echo === Kavach setup ===
where python >nul 2>nul || (echo Python not found. Install Python 3.12 from python.org and tick "Add Python to PATH". & pause & exit /b 1)
if not exist .venv (python -m venv .venv)

rem Repair a .venv that has no pip
.venv\Scripts\python -m pip --version >nul 2>nul || .venv\Scripts\python -m ensurepip --upgrade
.venv\Scripts\python -m pip --version >nul 2>nul || (echo Rebuilding .venv ... & python -m venv --clear .venv & .venv\Scripts\python -m ensurepip --upgrade)
.venv\Scripts\python -m pip --version >nul 2>nul || (echo. & echo pip is still missing. Reinstall Python from python.org ^(tick "Add Python to PATH"^), then run setup again. & pause & exit /b 1)

.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt || (echo. & echo Installing packages failed. Send a screenshot of this window. & pause & exit /b 1)
if not exist .env (copy .env.example .env >nul & echo Created .env - open it in Notepad and paste your SARVAM_API_KEY.)
echo.
echo Setup done. Now run: run.bat
pause
