@echo off
setlocal
cd /d "%~dp0"
title Surface Laptop 4 - Automated Tahoe Quick Start
set "SL4_MODE=Auto"
if /I "%~1"=="advanced" set "SL4_MODE=Menu"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\QuickStart-Windows.ps1" -Mode %SL4_MODE%
if errorlevel 1 (
  echo.
  echo Preparation stopped. Windows and Steam have not been erased.
)
echo.
pause
