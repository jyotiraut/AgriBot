@REM @echo off
@REM echo Starting Crop Advisor...
@REM echo.

@REM echo Starting FastAPI backend on port 8000...
@REM start cmd /k "cd /d %~dp0 && venv\Scripts\activate && uvicorn api.main:app --reload --port 8000"

@REM timeout /t 3 /nobreak > nul

@REM echo Starting Streamlit frontend on port 8501...
@REM start cmd /k "cd /d %~dp0 && venv\Scripts\activate && streamlit run ui/app.py"

@REM echo.
@REM echo FastAPI docs : http://localhost:8000/docs
@REM echo Streamlit app: http://localhost:8501


@REM echo.
@REM echo NOTE: Streamlit URL is http://localhost:8501
@REM echo       Do NOT add any path after the port number.
@REM echo       All API routes are at http://localhost:8000
@REM echo.

@echo off
echo Starting Crop Advisor...
echo.

echo Starting FastAPI backend on port 8000...
start cmd /k "cd /d %~dp0 && venv\Scripts\activate && uvicorn api.main:app --reload --port 8000"

timeout /t 3 /nobreak > nul

echo Starting Streamlit frontend on port 8005...
start cmd /k "cd /d %~dp0 && venv\Scripts\activate && streamlit run ui/app.py --server.port 8005"

echo.
echo ================================
echo  FastAPI  : http://localhost:8000
echo  API Docs : http://localhost:8000/docs
echo  Dashboard: http://localhost:8005/Dashboard
echo ================================
pause