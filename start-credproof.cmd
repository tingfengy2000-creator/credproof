@echo off
cd /d "%~dp0"
python -m agent_pilot.launch --demo --mode view
pause
