"""实机截屏: 书架页 OCR 基准（修 pipeline 用）。"""
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
shot = client.screencap()
out = _ROOT / "runtime/screenshots/audit_shelf_now.png"
out.write_bytes(shot.data if hasattr(shot, "data") else shot)
ocr = client.recognize("OCR", {}, shot)
detail = ocr.detail if isinstance(ocr.detail, dict) else {}
items = detail.get("all") or detail.get("boxes") or detail.get("items") or []
print(f"[shelf] {len(items)} boxes:")
for it in items:
    if isinstance(it, dict) and "box" in it and "text" in it:
        x, y, w, h = it["box"]
        print(f"   ({x},{y},{w},{h}) {str(it['text'])[:36]}")
client.close()
