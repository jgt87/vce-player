@echo off
cd /d "%~dp0"
python player.py
if errorlevel 1 pause
