#!/bin/bash
# SpamShield - one-command start (Linux / Mac)
pip install -r requirements.txt
uvicorn backend.main:app
# Then open: http://127.0.0.1:8000
