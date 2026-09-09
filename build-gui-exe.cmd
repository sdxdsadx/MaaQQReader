@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

set "PYEXE="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYEXE=%ROOT%\.venv\Scripts\python.exe"
if not defined PYEXE (
  py -3.10 -c "import sys" >nul 2>nul && set "PYEXE=py -3.10"
)
if not defined PYEXE (
  python -c "import sys" >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
  echo [ERROR] Python 3.10 not found.
  pause
  exit /b 2
)

echo [BUILD] Building dist\QQReaderGUI.exe ...
%PYEXE% -m PyInstaller --noconfirm --clean --onefile --windowed --name QQReaderGUI --paths "%ROOT%" "%ROOT%\gui\maa_qq_reader_gui.py"

if errorlevel 1 (
  echo.
  echo [ERROR] Build failed.
  pause
  exit /b 1
)

echo.
echo [OK] dist\QQReaderGUI.exe
echo Put the exe in this repo root before running it; it uses local Python 3.10 for scripts\\run_task.py.
pause
endlocal

