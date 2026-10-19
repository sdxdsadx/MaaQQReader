"""找到「第348章」入口 (303,217)。点它进正文。然后启动 300 分钟看护
（用 _autoread_final300.py，但书已切换无需导航）。"""
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
s = client.screencap()
ch = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "第348章" in t]
t, b = ch[0]
client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
time.sleep(4)
s2 = client.screencap()
texts = client.recognize("OCR", {}, s2).all_texts()
print("正文:", " | ".join(texts[:5])[:120], flush=True)
client.close()
