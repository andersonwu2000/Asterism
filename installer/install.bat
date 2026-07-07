@echo off
rem Asterism one-click installer — double-click me.
rem Everything happens in the PowerShell script; this wrapper only
rem exists because double-clicking a .ps1 opens Notepad.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
pause
