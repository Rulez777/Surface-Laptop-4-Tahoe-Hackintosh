@echo off
setlocal
cd /d "%~dp0"
title Surface Laptop 4 - Tahoe Quick Start
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\QuickStart-Windows.ps1" -Mode Menu
if errorlevel 1 (
  echo.
  echo Preparation stopped. Your Windows installation has not been overwritten.
)
echo.
pause
