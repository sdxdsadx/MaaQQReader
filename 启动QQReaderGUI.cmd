@echo off

rem ============================================================
rem  QQReader GUI 启动器（日常使用）；排障/调试请用 调试QQReader.cmd
rem  1) 定位 Python 3.10
rem  2) 找模拟器（MuMu 12 / 雷电 / BlueStacks 5 / 夜神 / 逍遥 / 任意 adb 设备）与真实 adb 端口
rem  3) 模拟器未启动则自动拉起（MuMu / 雷电 / 逍遥），等 adb 可连接 + boot 完成，检查分辨率
rem  4) 回写 configs\qqreader.local.json 的 adb_path / adb_address（没有本机配置时按示例生成）
rem  5) 设好 PYTHONPATH 后启动 GUI：默认打开 MFAAvalonia（mfa\MFAAvalonia.exe）；
rem     加参数 classic（启动QQReaderGUI.cmd classic）打开旧的 Tkinter GUI
rem ============================================================
setlocal EnableExtensions EnableDelayedExpansion
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
rem Use captcha.solver from local config; discard inherited one-off overrides.
set "QQREADER_CAPTCHA_SOLVER="
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "CONFIG=%ROOT%configs\qqreader.local.json"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass -Command"

rem ---------- 1) 定位 Python ----------
set "PYEXE="
if exist "%CONFIG%" (
  for /f "usebackq delims=" %%i in (`%PS% "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); $OutputEncoding = [Console]::OutputEncoding; try{(Get-Content -Raw -Encoding UTF8 -LiteralPath '%CONFIG%' ^| ConvertFrom-Json).machine.python_executable}catch{}"`) do set "PYCFG=%%i"
)
if defined PYCFG if exist "%PYCFG%" set "PYEXE=%PYCFG%"
if not defined PYEXE if exist "%ROOT%.venv\Scripts\python.exe" set "PYEXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYEXE ( py -3.10 -c "import sys" >nul 2>nul && set "PYEXE=py -3.10" )
if not defined PYEXE ( python -c "import sys" >nul 2>nul && set "PYEXE=python" )
if not defined PYEXE (
  echo [ERROR] 未找到 Python 3.10。请安装 Python 3.10 或创建 .venv。
  pause
  exit /b 2
)

rem ---------- 2-5) 找模拟器 / 设备，必要时拉起，等启动完成，检查分辨率，回写配置 ----------
rem 由 qqreader.maa.emulator 完成（MuMu 12 / 雷电 / BlueStacks 5 / 夜神 / 逍遥 / 任意 adb 设备）：
rem 安装目录读配置与注册表，不写死盘符；端口读模拟器管理工具，不写死端口。
rem Multi-instance: set QQREADER_EMULATOR_INDEX=N before running (default 0).
set "PYTHONPATH=%ROOT%"
if "!PYTHONPATH:~-1!"=="\" set "PYTHONPATH=!PYTHONPATH:~0,-1!"
%PYEXE% -m qqreader.maa.emulator prepare --launch --config "%CONFIG%" --example "%ROOT%configs\qqreader.example.json"
if errorlevel 1 echo [warn] 未找到在线的模拟器/设备，仍继续启动 GUI（GUI 内还会重试）。

rem ---------- 6) 启动 GUI ----------
echo [env] PYTHONPATH=!PYTHONPATH!

if /i "%~1"=="classic" goto :launch_classic

rem ---------- 6a) 默认：MFAAvalonia ----------
set "MFAEXE=%ROOT%mfa\MFAAvalonia.exe"
if not exist "%MFAEXE%" (
  echo [ERROR] 未找到 %MFAEXE%
  echo         请从 https://github.com/MaaXYZ/MFAAvalonia/releases 下载 v2.16.2 win-x64 并解压到 mfa\
  echo         或运行 启动QQReaderGUI.cmd classic 打开旧 GUI。
  pause
  exit /b 3
)
%PYEXE% -c "import maa" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 当前 Python 未安装 MaaFw（MFAAvalonia 的 Agent 需要它）。请运行：
  echo         %PYEXE% -m pip install "MaaFw==5.12.3"
  echo         或运行 启动QQReaderGUI.cmd classic 打开旧 GUI。
  pause
  exit /b 4
)
rem MFA 以 interface.json 中的 "python" 启动 Agent：把本 Python 所在目录放到 PATH 最前面。
set "PYDIR="
for /f "usebackq delims=" %%D in (`%PYEXE% -c "import os,sys;print(os.path.dirname(sys.executable))"`) do set "PYDIR=%%D"
if defined PYDIR (
  set "PATH=!PYDIR!;!PATH!"
  echo [env] Agent Python 目录: !PYDIR!
) else (
  echo [warn] 未能取得 Python 所在目录，Agent 将使用 PATH 中的 python。
)
rem mfa\config 不入库：新的 MFA 目录没有「教程已完成」标记，每次都会弹新手教程，启动前先写入。
%PYEXE% -m qqreader.mfa.first_use "%ROOT%mfa"
echo [env] 启动 MFAAvalonia ...
start "" /D "%ROOT%mfa" "%MFAEXE%"
endlocal
exit /b 0

rem ---------- 6b) classic：旧 Tkinter GUI ----------
:launch_classic
echo [env] 启动 QQReader GUI（classic）...
if exist "%CONFIG%" (
  %PYEXE% -m qqreader.gui --config "%CONFIG%"
) else (
  %PYEXE% -m qqreader.gui
)

if errorlevel 1 (
  echo.
  echo [ERROR] GUI 启动失败（exit=%errorlevel%）。请检查上面的输出。
  pause
)
endlocal
exit /b 0
