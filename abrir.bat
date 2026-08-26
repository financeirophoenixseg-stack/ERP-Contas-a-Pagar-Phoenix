@echo off
cd /d "%~dp0"
start "" http://localhost:8501
.venv\Scripts\streamlit.exe run app.py
