"""页面跳转中/OCR 少——等 2.5s 重拍全页。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
time.sleep(2.5)
s = client.screencap()
for t, b in sorted(client.recognize("OCR", {}, s).text_boxes(), key=lambda x: x[1][1])[:14]:
    print(f"y={b[1]:4d} | {t}")
client.close()
