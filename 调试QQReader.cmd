@echo off
chcp 936 >nul
rem  本文件以 GBK 保存：cmd 在 chcp 65001 下解析 UTF-8 中文批处理会错位，导致部分行被当成命令执行。
rem ============================================================================
rem  QQReader 调试 / 冷启动 / 体检（合并自原 冷启动QQReader.cmd）
rem  日常使用请双击「启动QQReaderGUI.cmd」；本脚本只在排障、调试时使用。
rem
rem  双击：弹出菜单选择模式（结束后窗口不关，方便看输出）
rem  命令行：调试QQReader.cmd [模式] [/cold] [/force]
rem
rem  模式:
rem    gui      冷启动环境后打开 GUI              (默认)
rem    run      冷启动环境后直接跑每日全链路 (daily_all.py)
rem    smoke    冷启动环境后做一次页面识别检查 (SmokeTest，输出状态/OCR)
rem    task     冷启动环境后单独跑一个任务 (会询问任务名和分钟数)
rem    test     只跑单元测试 (python -m pytest)，不碰设备
rem    stop     冷停止: 关 GUI + 关模拟器 + 清 adb
rem    status   只体检环境, 不做任何变更
rem
rem  选项:
rem    /cold    彻底重启模拟器 (先 shutdown 再 launch)
rem    /force   忽略「已有任务在跑」的保护
rem
rem  冷启动做了什么 (相对普通启动的差别):
rem    1. adb kill-server 清掉残留/offline 设备, 再 start-server
rem    2. 从 MuMuManager 读实例真实 adb 端口 (端口会漂移, 不写死)
rem    3. 模拟器没跑就拉起; 加 /cold 则先关机再开机
rem    4. 等 adb 可连接 + sys.boot_completed=1
rem    5. 端口与配置不一致时回写配置 (无 BOM)
rem    6. 拉起 QQ 阅读并清开屏弹窗, 把设备带到"可跑任务"状态
rem    7. 按模式交棒: GUI / 全链路 / 识别检查 / 单任务
rem ============================================================================
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

set "MODE=gui"
set "COLD="
set "FORCE="
set "INTERACTIVE="
if "%~1"=="" goto menu

rem ============================== 参数解析 ==============================
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="gui"    set "MODE=gui"    && shift && goto parse_args
if /i "%~1"=="run"    set "MODE=run"    && shift && goto parse_args
if /i "%~1"=="stop"   set "MODE=stop"   && shift && goto parse_args
if /i "%~1"=="smoke"  set "MODE=smoke"  && shift && goto parse_args
if /i "%~1"=="task"   set "MODE=task"   && shift && goto parse_args
if /i "%~1"=="test"   set "MODE=test"   && shift && goto parse_args
if /i "%~1"=="status" set "MODE=status" && shift && goto parse_args
if /i "%~1"=="/cold"  set "COLD=1"      && shift && goto parse_args
if /i "%~1"=="/force" set "FORCE=1"     && shift && goto parse_args
if /i "%~1"=="-h"     goto show_help
if /i "%~1"=="--help" goto show_help
if /i "%~1"=="/?"     goto show_help
echo [warn] 未知参数: %~1
shift
goto parse_args
:args_done
goto after_menu

rem ============================== 菜单 (双击时) ==============================
:menu
set "INTERACTIVE=1"
echo.
echo ================ QQReader 调试菜单 ================
echo   1. 环境体检 (不做任何变更)
echo   2. 冷启动环境 + 打开 GUI
echo   3. 彻底重启模拟器 (/cold) + 打开 GUI
echo   4. 冷启动环境 + 页面识别检查 (SmokeTest)
echo   5. 冷启动环境 + 单独运行一个任务
echo   6. 运行单元测试
echo   7. 冷停止 (关 GUI + 关模拟器 + 清 adb)
echo   0. 退出
echo ===================================================
choice /c 12345670 /n /m "请选择 [1-7, 0 退出]: "
set "PICK=%errorlevel%"
if "%PICK%"=="1" set "MODE=status"
if "%PICK%"=="2" set "MODE=gui"
if "%PICK%"=="3" set "MODE=gui" & set "COLD=1"
if "%PICK%"=="4" set "MODE=smoke"
if "%PICK%"=="5" set "MODE=task"
if "%PICK%"=="6" set "MODE=test"
if "%PICK%"=="7" set "MODE=stop"
if "%PICK%"=="8" exit /b 0

:after_menu

rem ============================== 定位 Python ==============================
set "PYEXE="
if exist "%CONFIG%" (
  for /f "usebackq delims=" %%i in (`%PS% "try{ $j=Get-Content -Raw -Encoding UTF8 -LiteralPath '%CONFIG%' | ConvertFrom-Json; Write-Host $j.machine.python_executable }catch{}"`) do set "PYCFG=%%i"
)
chcp 936 >nul
if defined PYCFG if exist "%PYCFG%" set "PYEXE=%PYCFG%"
if not defined PYEXE if exist "%ROOT%.venv\Scripts\python.exe" set "PYEXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYEXE ( py -3.10 -c "import sys" >nul 2>nul && set "PYEXE=py -3.10" )
if not defined PYEXE ( python -c "import sys" >nul 2>nul && set "PYEXE=python" )
if not defined PYEXE (
  echo [ERROR] 未找到 Python 3.10。请安装 Python 3.10 或创建 .venv。
  pause
  exit /b 2
)
chcp 936 >nul

set "PYTHONPATH=%ROOT%"
if "!PYTHONPATH:~-1!"=="\" set "PYTHONPATH=!PYTHONPATH:~0,-1!"

rem ============================== 模式: test ==============================
if /i "%MODE%"=="test" (
  echo.
  echo ============ 运行单元测试 ============
  %PYEXE% -m pytest -q -p no:cacheprovider
  set "RC=!errorlevel!"
  echo ============ pytest exit=!RC! ============
  goto finish
)
chcp 936 >nul

rem ============================== 模式: task 参数 ==============================
if /i "%MODE%"=="task" (
  echo.
  echo 可选任务: DailyReadingFlow DailyAudiobookFlow DailyGameFlow DailyAdFlow
  echo           DailyLevelAdFlow DailyExternalAppFlow ClaimOneReward ClaimAudiobookReward
  set /p "TASKNAME=任务名: "
  set "TASKMIN="
  set /p "TASKMIN=分钟数 (阅读/听书/游戏时长; 其他任务直接回车): "
  if not defined TASKNAME (
    echo [ERROR] 未输入任务名。
    goto finish
  )
)
chcp 936 >nul

rem ============================== 运行态检测 ==============================
call :detect_task
chcp 936 >nul
call :detect_gui
chcp 936 >nul

rem ============================== 模式: status ==============================
if /i "%MODE%"=="status" goto mode_status

rem ============================== 模式: stop ==============================
if /i "%MODE%"=="stop" goto mode_stop

rem ============================== 模式: gui / run ==============================

rem ---- 保护: 已有任务在跑时不做任何破坏性动作 ----
if defined TASKRUN if not defined FORCE (
  echo.
  echo [拒绝] 检测到任务正在运行 ^(run_task/daily_all PID=!TASKRUN!^)。
  echo        冷启动会重置 adb 并可能重启模拟器，会打断该任务。
  echo        请等任务结束，或确认后加 /force 强制执行。
  goto finish
)
chcp 936 >nul

rem ---- 保护: gui 模式且 GUI 已在运行 ----
if /i "%MODE%"=="gui" if defined GUIRUN if not defined FORCE (
  echo.
  echo [拒绝] QQReader GUI 已在运行 ^(PID=!GUIPID!^)，无需重复冷启动。
  echo        如需重开，请先关闭现有窗口，或加 /force 强制再开一个。
  goto finish
)
chcp 936 >nul

if not defined TASKRUN echo [env] 当前没有任务在运行，可以安全冷启动。

echo.
echo ============ 冷启动 QQReader ============
echo [env] 模式=%MODE%  Python=%PYEXE%
if defined COLD echo [env] 真冷启动: 会先关闭再重启模拟器实例 !VMINDEX!

rem ---- 1) 冷清 adb 残留 ----
if exist "%ADB%" (
  echo [env] 重置 adb 服务 ^(kill-server^) ...
  "%ADB%" kill-server >nul 2>nul
  "%ADB%" start-server >nul 2>nul
) else (
  echo [warn] 未找到 adb: %ADB%
)
chcp 936 >nul

rem ---- 2) 解析模拟器真实 adb 端口 ----
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
chcp 936 >nul
if defined ADBPORT (
  set "ADBADDR=127.0.0.1:!ADBPORT!"
) else (
  echo [env] 未能从 MuMuManager 读到端口，沿用配置文件中的 adb_address。
  if exist "%CONFIG%" (
    for /f "usebackq delims=" %%i in (`%PS% "try{ $j=Get-Content -Raw -Encoding UTF8 -LiteralPath '%CONFIG%' | ConvertFrom-Json; Write-Host $j.machine.adb_address }catch{}"`) do set "ADBADDR=%%i"
  )
)
chcp 936 >nul
if not defined ADBADDR set "ADBADDR=127.0.0.1:16384"
echo [env] 目标设备地址: %ADBADDR%

rem ---- 3) 模拟器就位 ----
if exist "%MUMUMGR%" (
  set "RUNNING="
  for /f "usebackq tokens=* delims=" %%L in (`"%MUMUMGR%" info -v %VMINDEX% 2^>nul`) do (
    echo %%L | findstr /c:"is_process_started" >nul && (
      echo %%L | findstr /c:"true" >nul && set "RUNNING=1"
    )
  )
  if defined COLD (
    if defined RUNNING (
      echo [env] /cold: 先关闭模拟器实例 %VMINDEX% ...
      "%MUMUMGR%" control -v %VMINDEX% shutdown >nul 2>nul
      call :wait_emu_stopped
    )
    echo [env] /cold: 启动模拟器实例 %VMINDEX% ...
    "%MUMUMGR%" control -v %VMINDEX% launch
  ) else (
    if defined RUNNING (
      echo [env] 模拟器已在运行 ^(复用; 加 /cold 可强制重启^)。
    ) else (
      echo [env] 模拟器未运行，正在启动实例 %VMINDEX% ...
      "%MUMUMGR%" control -v %VMINDEX% launch
    )
  )
)
chcp 936 >nul

rem ---- 4) 等 adb + boot 完成 ----
if exist "%ADB%" (
  echo [env] 等待 adb 连接 %ADBADDR% ...
  call :wait_adb
  if defined ADBOK (
    echo [env] adb 已连接 %ADBADDR%
    call :wait_boot
  ) else (
    echo [warn] 等待 adb 超时。请检查模拟器是否正常启动。
    if /i "%MODE%"=="run" (
      echo [ERROR] run 模式需要可用设备，已中止。
      goto finish
    )
  )
) else (
  echo [warn] 未找到 adb: %ADB%
)
chcp 936 >nul

rem ---- 5) 回写配置端口 (无 BOM) ----
if exist "%CONFIG%" (
  %PS% "$p='%CONFIG%'; $j=Get-Content -Raw -Encoding UTF8 -LiteralPath $p | ConvertFrom-Json; if($j.machine.adb_address -ne '%ADBADDR%'){ $j.machine.adb_address='%ADBADDR%'; $enc=New-Object System.Text.UTF8Encoding($false); $txt=$j | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($p,$txt,$enc); Write-Host ('[env] 已更新配置 adb_address -> ' + '%ADBADDR%') } else { Write-Host '[env] 配置端口与实际一致。' }"
)
chcp 936 >nul

rem ---- 6) 拉起 QQ 阅读并清开屏弹窗 ----
if defined ADBOK (
  echo [env] 启动 QQ 阅读并清理开屏弹窗 ...
  %PYEXE% "%ROOT%scripts\run_task.py" --config "%CONFIG%" --task LaunchQQReader --quiet
  if errorlevel 1 echo [warn] QQ 阅读启动/清理返回非零，继续。
)
chcp 936 >nul

rem ---- 7) 交棒 ----
if /i "%MODE%"=="run" (
  echo.
  echo [env] 开始执行每日全链路 ...
  echo.
  %PYEXE% "%ROOT%scripts\daily_all.py"
  set "RC=!errorlevel!"
  echo.
  echo ============ 冷启动 run 结束 exit=!RC! ============
  exit /b !RC!
)
chcp 936 >nul

if /i "%MODE%"=="smoke" (
  echo.
  echo [env] 页面识别检查 ^(SmokeTest^) ...
  %PYEXE% "%ROOT%scripts\run_task.py" --config "%CONFIG%" --task SmokeTest
  echo ============ SmokeTest exit=!errorlevel! ============
  goto finish
)
chcp 936 >nul

if /i "%MODE%"=="task" (
  set "EXTRA="
  if defined TASKMIN (
    if /i "!TASKNAME!"=="DailyGameFlow" (set "EXTRA=--duration-minutes !TASKMIN!") else (set "EXTRA=--minutes !TASKMIN!")
  )
  echo.
  echo [env] 单独运行 !TASKNAME! !EXTRA! ...
  %PYEXE% "%ROOT%scripts\run_task.py" --config "%CONFIG%" --task !TASKNAME! !EXTRA!
  echo ============ !TASKNAME! exit=!errorlevel! ============
  goto finish
)
chcp 936 >nul

echo.
echo [env] 环境就绪，打开 QQReader GUI ...
%PYEXE% -m qqreader.gui --config "%CONFIG%"
set "RC=!errorlevel!"
chcp 936 >nul
if not "!RC!"=="0" (
  echo.
  echo [ERROR] GUI 启动失败 ^(exit=!RC!^)。请检查上面的输出。
  pause
)
chcp 936 >nul
endlocal
exit /b 0

rem ============================== 模式: status ==============================
:mode_status
echo.
echo ============ QQReader 环境体检 ============
echo [python] %PYEXE%
if defined TASKRUN (echo [任务] 正在运行: PID=!TASKRUN!) else (echo [任务] 无任务在跑)
if defined GUIRUN (echo [GUI ] 正在运行: PID=!GUIPID!) else (echo [GUI ] 未运行)

set "STPORT="
set "STPROC="
set "STSTATE="
if exist "%MUMUMGR%" (
  for /f "usebackq tokens=* delims=" %%L in (`"%MUMUMGR%" info -v %VMINDEX% 2^>nul`) do (
    set "LINE=%%L"
    echo !LINE! | findstr /c:"adb_port" >nul && (
      for /f "tokens=2 delims=:" %%P in ("!LINE!") do (
        set "RAW=%%P"
        set "RAW=!RAW:,=!"
        set "RAW=!RAW: =!"
        set "STPORT=!RAW!"
      )
    )
    echo !LINE! | findstr /c:"is_process_started" >nul && (
      echo !LINE! | findstr /c:"true" >nul && set "STPROC=1"
    )
    echo !LINE! | findstr /c:"player_state" >nul && (
      for /f "tokens=2 delims=:" %%S in ("!LINE!") do (
        set "SRAW=%%S"
        set "SRAW=!SRAW:,=!"
        set "SRAW=!SRAW:"=!"
        set "SRAW=!SRAW: =!"
        set "STSTATE=!SRAW!"
      )
    )
  )
)
chcp 936 >nul
if defined STPROC (echo [模拟器] 进程已启动) else (echo [模拟器] 进程未启动)
if defined STPORT (echo [模拟器] adb 端口 !STPORT!) else (echo [模拟器] adb 端口 未知)
if defined STSTATE echo [模拟器] 状态 !STSTATE!

if exist "%CONFIG%" (
  for /f "usebackq delims=" %%i in (`%PS% "try{ $j=Get-Content -Raw -Encoding UTF8 -LiteralPath '%CONFIG%' | ConvertFrom-Json; Write-Host $j.machine.adb_address }catch{}"`) do set "CFGADDR=%%i"
)
chcp 936 >nul
echo [配置] adb_address = !CFGADDR!
if defined STPORT (
  set "EXPECT=127.0.0.1:!STPORT!"
  if /i "!CFGADDR!"=="!EXPECT!" (
    echo [配置] 与模拟器实际端口一致
  ) else (
    echo [配置] 不一致^^! 配置=!CFGADDR! 实际=!EXPECT!  ^(冷启动会自动纠正^)
  )
)
chcp 936 >nul

if exist "%ADB%" (
  echo [adb  ] devices:
  "%ADB%" devices
)
chcp 936 >nul
goto finish

rem ============================== 模式: stop ==============================
:mode_stop
echo.
echo ============ 冷停止 QQReader ============
if defined TASKRUN if not defined FORCE (
  echo [拒绝] 检测到任务正在运行 ^(PID=!TASKRUN!^)，已中止。
  echo        如确认要强停，请加 /force。
  goto finish
)
chcp 936 >nul
if defined GUIRUN (
  echo [stop] 关闭 QQReader GUI ^(PID=!GUIPID!^) ...
  %PS% "Get-Process | Where-Object { $_.MainWindowTitle -like '*QQReader*' } | Stop-Process -Force" >nul 2>nul
) else (
  echo [stop] GUI 未在运行。
)
chcp 936 >nul
if defined TASKRUN if defined FORCE (
  echo [stop] 强制结束任务 PID=!TASKRUN! ...
  taskkill /PID !TASKRUN! /T /F >nul 2>nul
)
chcp 936 >nul
if exist "%MUMUMGR%" (
  echo [stop] 关闭模拟器实例 %VMINDEX% ...
  "%MUMUMGR%" control -v %VMINDEX% shutdown
)
chcp 936 >nul
if exist "%ADB%" (
  echo [stop] 清理 adb 服务 ...
  "%ADB%" kill-server >nul 2>nul
)
chcp 936 >nul
echo [stop] 冷停止完成。
goto finish

rem ============================== 结束 ==============================
:finish
if defined INTERACTIVE (
  echo.
  pause
)
chcp 936 >nul
exit /b 0

rem ============================== 子过程 ==============================
:detect_task
set "TASKRUN="
for /f "usebackq delims=" %%i in (`%PS% "$p=Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'run_task' }; if($p){ $p.ProcessId -join ',' } else { '' }"`) do set "TASKRUN=%%i"
chcp 936 >nul
if not defined TASKRUN (
  for /f "usebackq delims=" %%i in (`%PS% "$p=Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'daily_all' }; if($p){ $p.ProcessId -join ',' } else { '' }"`) do set "TASKRUN=%%i"
)
chcp 936 >nul
exit /b 0

:detect_gui
set "GUIRUN="
set "GUIPID="
for /f "usebackq delims=" %%i in (`%PS% "$g=Get-Process | Where-Object { $_.MainWindowTitle -like '*QQReader*' }; if($g){ $g.Id -join ',' } else { '' }"`) do set "GUIPID=%%i"
chcp 936 >nul
if defined GUIPID set "GUIRUN=1"
exit /b 0

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
chcp 936 >nul
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
chcp 936 >nul
if defined BOOTOK (echo [env] Android 已启动完成。) else (echo [warn] 等待 boot_completed 超时，仍继续。)
exit /b 0

:wait_emu_stopped
set "STILL="
for /l %%N in (1,1,30) do (
  if not defined STILL (
    set "STILL="
    for /f "usebackq tokens=* delims=" %%L in (`"%MUMUMGR%" info -v %VMINDEX% 2^>nul`) do (
      echo %%L | findstr /c:"is_process_started" >nul && (
        echo %%L | findstr /c:"true" >nul && set "STILL=1"
      )
    )
    if defined STILL ping -n 3 127.0.0.1 >nul
  )
)
chcp 936 >nul
exit /b 0

:show_help
echo.
echo QQReader 调试脚本
echo.
echo   调试QQReader.cmd [模式] [/cold] [/force]
echo.
echo   模式:
echo     gui      冷启动环境后打开 GUI              (默认)
echo     run      冷启动环境后直接跑每日全链路
echo     smoke    冷启动环境后做页面识别检查
echo     task     冷启动环境后单独运行一个任务
echo     test     只跑单元测试
echo     stop     冷停止: 关 GUI + 关模拟器 + 清 adb
echo     status   只体检环境, 不做任何变更
echo.
echo   选项:
echo     /cold    彻底重启模拟器 (先 shutdown 再 launch)
echo     /force   忽略「已有任务在跑」的保护
echo.
exit /b 0
