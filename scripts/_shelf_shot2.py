"""实机核验: 退出阅读页后回书架，确认听书入口 OCR 预期是否匹配当前 UI。"""
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
# 此刻应已退到书架（阅读修复轮结束时按了 BACK）
shot = client.screencap()
ocr = client.recognize("OCR", {}, shot)
detail = ocr.detail if isinstance(ocr.detail, dict) else {}
items = detail.get("all") or detail.get("boxes") or detail.get("items") or []
print(f"[page] {len(items)} boxes:")
for it in items:
    if isinstance(it, dict) and "box" in it and "text" in it:
        x, y, w, h = it["box"]
        print(f"   ({x},{y},{w},{h}) {str(it['text'])[:40]}")
client.close()
