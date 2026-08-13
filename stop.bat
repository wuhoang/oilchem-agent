@echo off
title OilChem Agent - Stop

echo.
echo ================================================
echo   OilChem Agent - Stop Services
echo ================================================
echo.

echo [1/2] Stopping backend (port 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo      Done.

echo.
echo [2/2] Stopping frontend (port 5173)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo      Done.

echo.
echo ================================================
echo   All services stopped.
echo ================================================
echo.
timeout /t 3 >nul