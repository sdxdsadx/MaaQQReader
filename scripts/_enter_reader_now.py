"""页面回到了书架（下滑滑过头出简介页）。书架上有「1章/456章」续读行。
点它进正文 → 跑 300 分钟自动阅读主脚本（跳过前置导航，直接从 is_auto_reading
开始）。做一个精简启动：点续读行 → 等 → 调 _autoread_300.py 的看护部分。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()

s = client.screencap()
progress = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "章/" in t]
print("续读行:", progress, flush=True)
t, b = progress[0]
client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
time.sleep(3.5)
s2 = client.screencap()
texts = client.recognize("OCR", {}, s2).all_texts()
print("进入:", " | ".join(texts[:6])[:120], flush=True)
client.close()
