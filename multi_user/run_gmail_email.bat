@echo off

echo Activating virtual environment...
call venv\Scripts\activate

echo Starting Gmail Email app...

streamlit run gmail_email.py

echo.
echo ==========================================
echo   Gmail Email app is running successfully!
echo   Open: http://localhost:8502
echo ==========================================

pause