"""补差 1 分钟阅读：DirectReadingFlow 已在正文页（华娱书）。
先确认正文页状态，然后跑 auto_read 3 分钟（1 分钟差 + 缓冲）。"""
import sys
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
texts = client.recognize("OCR", {}, s).all_texts()
print("当前页:", " | ".join(texts[:8])[:140])
client.close()
