"""MAA 流程 SUCCESS 但 app 还停在正文页（DirectReadingFlow 成功链不包含
退出正文——挂机后流程结束）。手动：BACK 退出正文 → 回书架 → 点时长兑赠币
进奖励页领取。"""
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
time.sleep(2.5)

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
shelf = [(t, b) for t, b in boxes if "书架" in t and b[1] > 1100]
reward_entry = [(t, b) for t, b in boxes if "兑赠币" in t]
print("书架tab:", bool(shelf), "| 时长兑赠币入口:", reward_entry[:1], flush=True)
if reward_entry:
    t, b = reward_entry[0]
    client.swipe(b[0] + 100, b[1] + 10, b[0] + 100, b[1] + 10, 60)
    time.sleep(3)
    s2 = client.screencap()
    for t2, b2 in sorted(client.recognize("OCR", {}, s2).text_boxes(),
                         key=lambda x: x[1][1]):
        if any(k in t2 for k in ("已获赠币", "再读", "已读", "听书", "领取", "分钟")):
            print(f"y={b2[1]:4d} x={b2[0]:4d} w={b2[2]:3d} | {t2}", flush=True)
client.close()
