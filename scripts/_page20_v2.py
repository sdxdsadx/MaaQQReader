"""书架页（15分钟）。点续读行进正文（先 OCR 找 章/ 行），确认正文页后翻页 20 分钟。"""
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

# 多次尝试找续读行
progress = []
for attempt in range(3):
    s = client.screencap()
    progress = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "章/" in t]
    if progress:
        break
    time.sleep(2)
print("续读行:", progress, flush=True)
if not progress:
    sys.exit("未找到续读行，需人工处理")

t, b = progress[0]
client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
time.sleep(3.5)

# 确认正文页（有"第N章"或正文特征）
s = client.screencap()
texts = client.recognize("OCR", {}, s).all_texts()
joined = " ".join(texts)
in_reader = ("第" in joined and "章" in joined) or len(joined) > 200
print("正文确认:", in_reader, joined[:80], flush=True)

if in_reader:
    t0 = time.time()
    taps = 0
    while time.time() - t0 < 20 * 60:
        subprocess.run([adb, "-s", dev, "shell", "input", "tap", "600", "640"],
                       capture_output=True, timeout=15)
        taps += 1
        time.sleep(18)
    print(f"翻页 {taps} 次", flush=True)
    subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=15)
    time.sleep(2.5)
    s = client.screencap()
    entry = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
             if "兑赠币" in t or "领20赠币" in t]
    if entry:
        t, b = entry[-1]
        client.swipe(b[0] + 100, b[1] + 10, b[0] + 100, b[1] + 10, 60)
        time.sleep(3)
        s2 = client.screencap()
        for t2, b2 in sorted(client.recognize("OCR", {}, s2).text_boxes(),
                             key=lambda x: x[1][1]):
            if any(k in t2 for k in ("已获赠币", "再读", "领取", "分钟")):
                print(f"y={b2[1]:4d} x={b2[0]:4d} w={b2[2]:3d} | {t2}", flush=True)
client.close()
