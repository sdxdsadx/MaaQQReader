"""意外弹出了「安装未知应用」系统授权页（QQ阅读 8.2.3.888 更新安装请求）！
横屏布局。需要点「允许来自此来源的应用」开关或返回。
这解释了之前书架点击无效——QQ阅读触发了应用内更新弹窗序列。
处理：BACK 退出该页（拒绝更新），回 QQ阅读。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"
subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
               capture_output=True, timeout=15)
time.sleep(3)

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1])[:10]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
