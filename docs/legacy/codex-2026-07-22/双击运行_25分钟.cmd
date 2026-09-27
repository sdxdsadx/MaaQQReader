@echo off
chcp 65001 >nul
cd /d "%~dp0"
title QQ阅读自动任务（25分钟）
echo 正在启动 QQ 阅读自动任务……
"D:\python\python.exe" "%~dp0qqreader_automation.py" --minutes 25
echo.
if errorlevel 1 (
  echo 执行未完成，请查看“自动点击日志.txt”和“最后画面.png”。
) else (
  echo 执行完成，MuMu 模拟器已关闭。
)
pause
