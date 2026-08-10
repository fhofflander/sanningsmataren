@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
  echo Programmet ar inte installerat an. Startar installationen...
  call "%~dp0install-gui.bat"
)

if not exist ".venv\Scripts\pythonw.exe" (
  echo Installationen blev inte klar. Las felmeddelandet ovan.
  pause
  exit /b 1
)

start "" /D "%~dp0" "%~dp0.venv\Scripts\pythonw.exe" -m debate_transcriber.gui
