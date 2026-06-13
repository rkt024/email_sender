@echo off

echo Activating virtual environment...
call venv\Scripts\activate

echo Starting Dolma Email app...

streamlit run dolma_email.py

echo.
echo ==========================================
echo   Dolma Email app is running successfully!
echo   Open: http://localhost:8502
echo ==========================================

pause