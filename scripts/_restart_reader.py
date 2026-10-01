"""返回箭头也无效——页面纹丝不动。这强烈暗示：**当前正文页上方盖着一个
透明全屏层**（听书会话的悬浮控制层？），所有点击都被它拦截。
用户说的「左下角自动阅读浮游框」可能此刻存在但 OCR 读不到（图形按钮无文字）。
截屏直接目视检查（保存 PNG 让 vision 看？没有 vision 工具——
改用 ADB 截屏导出后用 PIL 分析像素/或者发给用户看）。
更实用：直接重启 QQ阅读 app——彻底清掉所有会话状态（听书会话、浮窗）。
重启后从书架重新进书 → 无听书会话干扰 → 开自动阅读。这是最短路径。"""
import sys
import subprocess
import time
from pathlib import Path

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"
subprocess.run([adb, "-s", dev, "shell", "am", "force-stop", "com.qq.reader"],
               capture_output=True, timeout=20)
time.sleep(3)
subprocess.run([adb, "-s", dev, "shell",
                "monkey -p com.qq.reader -c android.intent.category.LAUNCHER 1"],
               capture_output=True, timeout=30)
time.sleep(14)
print("app 已重启")
