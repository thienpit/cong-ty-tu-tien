@echo off
title Cong Ty Tu Tien - Dang khoi dong...
echo.
echo ======================================
echo   Cong Ty Tu Tien - He thong giam sat
echo ======================================
echo.

REM Start server
echo [1/2] Khoi dong server...
cd /d "%~dp0\..\dashboard"
start /B "" "..\.venv\Scripts\python.exe" server.py
timeout /t 3 /nobreak >nul

REM Check server
curl -s http://localhost:8080 >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Server khong kha dung tren port 8080!
    echo.
    pause
    exit /b 1
)
echo [OK] Server dang chay tren http://localhost:8080
echo.

REM Start Electron
echo [2/2] Khoi dong app...
cd /d "%~dp0\electron"
node node_modules\electron\cli.js .
