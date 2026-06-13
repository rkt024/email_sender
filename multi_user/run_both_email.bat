@echo off

echo Activating virtual environment...
call venv\Scripts\activate

echo Starting both Email apps...

start cmd /k "streamlit run gmail_email.py --server.port 8505"
start cmd /k "streamlit run dolma_email.py --server.port 8506"

echo.
echo ==========================================
echo   Both Email apps are running successfully!
echo   Open: http://localhost:8505 for Gmail Email
echo   Open: http://localhost:8506 for Dolma Email
echo ==========================================

pause