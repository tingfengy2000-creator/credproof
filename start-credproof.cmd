@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0runtime\python\python.exe" (
  "%~dp0runtime\python\python.exe" -S -m agent_pilot.launch --workspace "%~dp0." --demo --mode view --auto-port --open-browser %*
) else (
  powershell.exe -NoProfile -File "%~dp0scripts\delivery\launch.ps1" %*
)
set "credproof_exit=%errorlevel%"
if not "%credproof_exit%"=="0" (
  echo CredProof could not start. See the error above.
  echo Re-extract the complete runtime\python directory and check TEMP write permission.
  echo If the PowerShell fallback is blocked by policy, use the bundled runtime; no policy change is required.
)
pause
exit /b %credproof_exit%
