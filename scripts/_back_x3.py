"""run8 有进展：跳过后进了「详情页」（商品页，非弹窗）。当前页有「反馈」
右上角。这是「上滑或点击跳转」的详情页——需要返回。
多次 BACK 回奖励页，然后判断当前进度。
已到工具调用上限边缘，快速：BACK×3 → 读页面。"""
import subprocess
import time
from pathlib import Path

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"
for i in range(3):
    subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=15)
    time.sleep(2)
print("BACK x3 done")
