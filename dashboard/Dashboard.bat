@echo off
title Cong Ty Tu Tiên - Dashboard
echo Dang khoi dong dashboard...
cd /d "%~dp0"
start "" http://localhost:8080
../.venv/Scripts/python.exe server.py
