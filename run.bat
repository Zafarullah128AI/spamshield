@echo off
REM SpamShield - one double-click start (Windows)
pip install -r requirements.txt
uvicorn backend.main:app
REM Then open: http://127.0.0.1:8000
