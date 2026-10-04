@echo off
setlocal
cd /d "%~dp0.."
set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  where py >nul 2>&1
  if errorlevel 1 (
    echo Python launcher py was not found. Install Python 3.12 first.
    exit /b 2
  )
  py -3.12 -m venv .venv
  if errorlevel 1 exit /b 2
)
"%PYTHON%" -m pip install -r agent_pilot\requirements-lock.txt
if errorlevel 1 exit /b 2
"%PYTHON%" -c "import qwen_agent, importlib.metadata as m; print('qwen-agent', m.version('qwen-agent'))"
if errorlevel 1 exit /b 2
"%PYTHON%" scripts\get_gitleaks.py
if errorlevel 1 exit /b 2
echo Local agent environment is ready.
echo Use .venv\Scripts\python.exe for tests and set CREDPROOF_GITLEAKS to .tools\gitleaks-8.28.0\gitleaks.exe.
endlocal
