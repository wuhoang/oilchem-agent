@echo off
title OilChem Agent - Start

cd /d "%~dp0"

echo.
echo ================================================
echo   OilChem Agent Launcher
echo ================================================
echo.

rem --- Find Python ---
set "PY_CMD="

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py -3"
    goto :python_found
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    python --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=python"
        goto :python_found
    )
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :python_found
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :python_found
)

echo [ERROR] Python 3.12+ not found.
echo Please install from: https://www.python.org/downloads/
echo NOTE: Check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:python_found
echo [OK] Python: %PY_CMD%
%PY_CMD% --version

rem --- Check Node.js ---
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Node.js 22+ not found.
    echo Please install from: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

echo [OK] Node.js
node --version

echo.
echo --- Starting services ---
echo.

rem --- Run Python launcher ---
%PY_CMD% start.py

if %errorlevel% neq 0 (
    echo.
    echo [Launcher] Errors occurred. See log above.
    pause
)
echo.
echo Press any key to close this window...
pause >nul