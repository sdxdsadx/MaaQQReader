"""页面几乎空白（只有状态栏和几个图标）——QQ阅读可能已退到后台/桌面。
重启 QQ阅读到前台，让 DailyGameFlow 能恢复（它有 LaunchQQReader 前置？）。"""
import subprocess
import time

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"
r = subprocess.run([adb, "-s", dev, "shell",
                    "monkey -p com.qq.reader -c android.intent.category.LAUNCHER 1"],
                   capture_output=True, text=True, timeout=30)
time.sleep(10)
r2 = subprocess.run([adb, "-s", dev, "shell", "pidof com.qq.reader"],
                    capture_output=True, text=True, timeout=15)
print("pid:", r2.stdout.strip())
