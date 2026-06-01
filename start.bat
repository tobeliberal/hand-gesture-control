@echo off
echo Starting Gesture Recognition System...
start "Backend" cmd /k "cd /d %~dp0backend && python main.py"
timeout /t 3 /nobreak >nul
start "Frontend" cmd /k "cd /d %~dp0web && npm run dev"
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
pause
