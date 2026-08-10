@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-windows.ps1" %*
if errorlevel 1 (
  echo.
  echo Installationen misslyckades.
  pause
  exit /b 1
)
echo.
echo Installationen ar klar. Dubbelklicka pa run-gui.bat for att starta.
pause
