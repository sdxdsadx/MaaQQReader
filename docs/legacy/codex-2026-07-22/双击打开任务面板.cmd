@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" "D:\python\pythonw.exe" "%~dp0qqreader_gui.py"
