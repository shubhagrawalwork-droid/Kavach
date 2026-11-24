@echo off
if not exist .venv (echo Run setup.bat first. & pause & exit /b 1)
echo Kavach is starting... open http://localhost:8000 in Chrome or Edge
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
