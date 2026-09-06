@echo off
setlocal
cd /d "%~dp0"
if exist "MaaQQReaderGUI.exe" (
    start "" "MaaQQReaderGUI.exe"
    exit /b 0
)
python "gui\maa_qq_reader_gui.py"
