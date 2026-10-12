@echo off
title ApexTrade - Autonom Handelsbot
cd /d "%~dp0"
echo Startar ApexTrade...
call venv\Scripts\python.exe run.py
pause
