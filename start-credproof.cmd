@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0scripts\delivery\launch.ps1" %*
pause
