"""修 unpack bug（target=(t,b) 元组，[1] 是整个 box）。重跑。"""
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
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
prog = [(t, b) for t, b in boxes if "3385" in t]
print("347章行:", prog, flush=True)
if prog:
    t, b = prog[0]
    client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:5])[:110], flush=True)
client.close()
