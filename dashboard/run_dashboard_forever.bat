@echo off
:loop
echo [%DATE% %TIME%] Starting Công Ty Tu Tiên Dashboard Server...
cd /d "%~dp0"
..\.venv\Scripts\python.exe server.py

echo [%DATE% %TIME%] !!! SERVER CRASHED OR EXITED !!!
echo Restarting in 5 seconds...
timeout /t 5
goto loop
