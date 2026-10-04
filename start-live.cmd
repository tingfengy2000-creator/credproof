@echo off
cd /d "%~dp0"
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" -c "import qwen_agent" >nul 2>&1
if errorlevel 1 (
  echo qwen-agent is unavailable in the selected Python environment.
  echo Run scripts\setup-local-agent.cmd first.
  pause
  exit /b 2
)
"%PYTHON%" -m agent_pilot.launch --demo --mode live
pause
