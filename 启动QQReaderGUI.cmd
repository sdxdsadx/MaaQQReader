@echo off
chcp 65001 >nul
rem ============================================================
rem  QQReader GUI 启动器（日常使用）；排障/调试请用 调试QQReader.cmd
rem  1) 定位 Python 3.10
rem  2) 用 MuMuManager 查询实例真实 adb 端口（不再写死端口）
rem  3) 模拟器未启动则自动拉起，并等 adb 可连接 + boot 完成
rem  4) 回写 configs\qqreader.local.json 的 adb_address
rem  5) 设好 PYTHONPATH 后启动 GUI：默认打开 MFAAvalonia（mfa\MFAAvalonia.exe）；
rem     加参数 classic（启动QQReaderGUI.cmd classic）打开旧的 Tkinter GUI
rem ============================================================
setlocal EnableExtensions EnableDelayedExpansion
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "CONFIG=%ROOT%configs\qqreader.local.json"
set "MUMU_DIR=D:\Program Files\Netease\MuMu Player 12\shell"
set "MUMUMGR=%MUMU_DIR%\MuMuManager.exe"
set "ADB=%MUMU_DIR%\adb.exe"
set "VMINDEX=0"
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

rem ---------- 2) 解析模拟器真实 adb 端口 ----------
set "ADBPORT="
set "ADBADDR="
if exist "%MUMUMGR%" (
  echo [env] 查询 MuMu 实例 %VMINDEX% 的 adb 端口...
  for /f "usebackq tokens=* delims=" %%L in (`"%MUMUMGR%" info -v %VMINDEX% 2^>nul`) do (
    set "LINE=%%L"
    echo !LINE! | findstr /c:"adb_port" >nul && (
      for /f "tokens=2 delims=:" %%P in ("!LINE!") do (
        set "RAW=%%P"
        set "RAW=!RAW:,=!"
        set "RAW=!RAW: =!"
        set "ADBPORT=!RAW!"
      )
    )
  )
)

if defined ADBPORT (
  set "ADBADDR=127.0.0.1:!ADBPORT!"
) else (
  echo [env] 未能从 MuMuManager 读到端口，沿用配置文件中的 adb_address。
  if exist "%CONFIG%" (
    for /f "usebackq delims=" %%i in (`%PS% "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); $OutputEncoding = [Console]::OutputEncoding; try{(Get-Content -Raw -Encoding UTF8 -LiteralPath '%CONFIG%' ^| ConvertFrom-Json).machine.adb_address}catch{}"`) do set "ADBADDR=%%i"
  )
)
if not defined ADBADDR set "ADBADDR=127.0.0.1:16384"
echo [env] 目标设备地址: %ADBADDR%

rem ---------- 3) 模拟器未启动则拉起 ----------
if exist "%MUMUMGR%" (
  set "RUNNING="
  for /f "usebackq tokens=* delims=" %%L in (`"%MUMUMGR%" info -v %VMINDEX% 2^>nul`) do (
    echo %%L | findstr /c:"is_process_started" >nul && (
      echo %%L | findstr /c:"true" >nul && set "RUNNING=1"
    )
  )
  if defined RUNNING (
    echo [env] 模拟器已在运行。
  ) else (
    echo [env] 模拟器未运行，正在启动实例 %VMINDEX% ...
    "%MUMUMGR%" control -v %VMINDEX% launch
  )
)

rem ---------- 4) 等 adb 就绪 ----------
if exist "%ADB%" (
  echo [env] 等待 adb 连接 %ADBADDR% ...
  call :wait_adb
  if defined ADBOK (
    echo [env] adb 已连接 %ADBADDR%
    call :wait_boot
  ) else (
    echo [warn] 等待 adb 超时，仍继续启动 GUI（GUI 内还会重试）。
  )
) else (
  echo [warn] 未找到 adb: %ADB%
)

rem ---------- 5) 端口变化时回写配置 ----------
if exist "%CONFIG%" (
  %PS% "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); $OutputEncoding = [Console]::OutputEncoding; $p='%CONFIG%'; $j=Get-Content -Raw -Encoding UTF8 -LiteralPath $p | ConvertFrom-Json; if($j.machine.adb_address -ne '%ADBADDR%'){ $j.machine.adb_address='%ADBADDR%'; $enc=New-Object System.Text.UTF8Encoding($false); $txt=$j | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($p,$txt,$enc); Write-Host ('[env] 已更新配置 adb_address -> ' + '%ADBADDR%') } else { Write-Host '[env] 配置端口与实际一致。' }"
)

rem ---------- 6) 启动 GUI ----------
set "PYTHONPATH=%ROOT%"
if "!PYTHONPATH:~-1!"=="\" set "PYTHONPATH=!PYTHONPATH:~0,-1!"
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

rem ============ 子过程 ============
:wait_adb
set "ADBOK="
for /l %%N in (1,1,60) do (
  if not defined ADBOK (
    "%ADB%" connect %ADBADDR% >nul 2>nul
    for /f "tokens=1,2" %%A in ('"%ADB%" devices 2^>nul') do (
      if /i "%%A"=="%ADBADDR%" if /i "%%B"=="device" set "ADBOK=1"
    )
    if not defined ADBOK ping -n 3 127.0.0.1 >nul
  )
)
exit /b 0

:wait_boot
echo [env] 等待 Android 启动完成...
set "BOOTOK="
for /l %%N in (1,1,60) do (
  if not defined BOOTOK (
    for /f "usebackq delims=" %%B in (`"%ADB%" -s %ADBADDR% shell getprop sys.boot_completed 2^>nul`) do (
      if "%%B"=="1" set "BOOTOK=1"
    )
    if not defined BOOTOK ping -n 3 127.0.0.1 >nul
  )
)
if defined BOOTOK (echo [env] Android 已启动完成。) else (echo [warn] 等待 boot_completed 超时，仍继续启动 GUI。)
exit /b 0