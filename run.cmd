@echo off
title ContentCascade Launcher
echo.
echo  ========================================
echo   ContentCascade - Starting Servers...
echo  ========================================
echo.

rem Resolve project root from the location of this script
set "PROJECT_ROOT=%~dp0"

echo [1/3] Starting Backend (FastAPI on port 8000)...
start "ContentCascade Backend" cmd /k "cd /d "%PROJECT_ROOT%backend" && python -m uvicorn main:app --reload --reload-exclude "pipeline_assets_*" --host 0.0.0.0 --port 8000"

echo [2/3] Starting Frontend (Next.js on port 3000)...
start "ContentCascade Frontend" cmd /k "cd /d "%PROJECT_ROOT%frontend" && npx next dev --port 3000"

echo [3/3] Waiting for servers to start...
timeout /t 8 /nobreak > nul

echo.
echo  Opening browser at http://localhost:3000 ...
start "" "http://localhost:3000"

echo.
echo  ========================================
echo   ContentCascade is running!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo  ========================================
echo.
echo  Press any key to close this launcher window.
pause > nul
