"""听书「立即领取」@ (550,617,w83) → 中心 (591,625)。点它领 20 赠币。"""
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
client.swipe(591, 625, 591, 625, 60)
time.sleep(3)
s = client.screencap()
for t, b in client.recognize("OCR", {}, s).text_boxes():
    if "今日已获赠币" in t:
        print("领取后:", t, flush=True)
        break
client.close()
