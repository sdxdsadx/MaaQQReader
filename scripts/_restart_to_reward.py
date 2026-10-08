"""多次点击入口行无效——昨天同样的入口 (200,199) 能进。差异：
今天书架页多了「中秋找玉兔/免费读一年」活动横幅（y 433-488），
可能整个书架列表区被活动浮层接管，点击被浮层拦截。
解法：先找活动弹窗的 X 关闭（OCR 没看到 X——可能在屏幕边缘）。
或者直接重启 app 回到干净书架（昨天重启后入口可点）。
用 force-stop → 跳过 → 书架 → 点入口。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()

def coins():
    s = client.screencap()
    for t, b in client.recognize("OCR", {}, s).text_boxes():
        if "今日已获赠币" in t:
            return t
    return None

subprocess.run([adb, "-s", dev, "shell", "am", "force-stop", "com.qq.reader"],
               capture_output=True, timeout=20)
time.sleep(3)
subprocess.run([adb, "-s", dev, "shell",
                "monkey -p com.qq.reader -c android.intent.category.LAUNCHER 1"],
               capture_output=True, timeout=30)
time.sleep(14)
s = client.screencap()
skip = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳过" in t]
if skip:
    t, b = skip[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
time.sleep(3)
s = client.screencap()
entry = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
         if "兑赠币" in t or "领20赠币" in t]
print("重启后入口:", entry, flush=True)
if entry:
    t, b = entry[-1]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(4)
    print("进奖励页:", coins(), flush=True)
client.close()
