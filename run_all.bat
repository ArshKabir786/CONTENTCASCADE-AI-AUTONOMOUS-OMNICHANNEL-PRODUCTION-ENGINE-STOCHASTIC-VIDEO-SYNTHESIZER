@echo off
rem Change to the project root directory
set "PROJECT_ROOT=%~dp0"

rem Start the backend FastAPI server in a new window
start "Backend" cmd /k "cd /d "%PROJECT_ROOT%backend" && uvicorn main:app --reload"

rem Start the frontend Next.js dev server in a new window
start "Frontend" cmd /k "cd /d "%PROJECT_ROOT%frontend" && npm run dev"

rem Give servers a moment to start
timeout /t 5 /nobreak > nul

rem Open the default browser to the frontend URL
start "" "http://localhost:3000"
