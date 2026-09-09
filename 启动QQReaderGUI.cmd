@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PYEXE="
if exist "%ROOT%.venv\Scripts\python.exe" set "PYEXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYEXE (
  py -3.10 -c "import sys" >nul 2>nul && set "PYEXE=py -3.10"
)
if not defined PYEXE (
  python -c "import sys" >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
  echo [ERROR] Python 3.10 not found. Install Python 3.10 or create .venv.
  pause
  exit /b 2
)

if "%~1"=="" (
  if exist "%ROOT%configs\qqreader.local.json" (
    %PYEXE% -m qqreader.gui --config "%ROOT%configs\qqreader.local.json"
  ) else (
    %PYEXE% -m qqreader.gui
  )
) else (
  %PYEXE% -m qqreader.gui %*
)

if errorlevel 1 (
  echo.
  echo [ERROR] GUI failed to start.
  pause
)
endlocal
