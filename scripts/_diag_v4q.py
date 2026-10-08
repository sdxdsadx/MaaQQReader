"""「立即观看」box=(554,353,?)——点它进广告，验证 12 层第 7 层可推进。
点击后 8 秒截图看广告页。"""
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
ocr = client.recognize("OCR", {}, s)
btn = None
for t, b in ocr.text_boxes():
    if "立即观看" in t:
        btn = b
        break
if btn is None:
    print("未找到立即观看")
    client.close()
    raise SystemExit(1)
x, y = btn[0] + btn[2] // 2, btn[1] + btn[3] // 2
print(f"点击 立即观看 ({x},{y})")
client.swipe(x, y, x, y, 80)
time.sleep(8)
s2 = client.screencap()
texts2 = client.recognize("OCR", {}, s2).all_texts()
print("=== 点击后页面 ===")
for t in texts2[:16]:
    print(t)
client.close()
