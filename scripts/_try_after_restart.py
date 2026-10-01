"""重启后直接恢复了第35章正文页（app 记住了上次位置），无浮窗、无菜单。
现在试开自动阅读：幂等菜单→设置→自动阅读→验证。若 toast 再现说明
重启也没杀掉朗读会话（不太可能），若成功→30分钟看护自动接管
（auto_read_30min.py 的 is_auto_reading 会检测到已在翻页 → 直接看护）。"""
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

def marks():
    s = client.screencap()
    return [t for t, b in client.recognize("OCR", {}, s).text_boxes()
            if any(k in t for k in ("设置", "自动阅读", "更多", "无法"))]

for _ in range(2):
    client.swipe(360, 640, 360, 640, 60); time.sleep(1.5)
    if "设置" in " ".join(marks()):
        break
client.swipe(452, 1247, 452, 1247, 60); time.sleep(1.5)
print("面板:", marks(), flush=True)
client.swipe(355, 1122, 355, 1122, 60); time.sleep(1.5)
print("点后:", marks(), flush=True)
client.swipe(360, 640, 360, 640, 0); time.sleep(1.5)

def first():
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    body = [(t, b) for t, b in boxes if 100 < b[1] < 1000 and b[0] < 600 and b[2] > 40]
    body.sort(key=lambda x: x[1][1])
    return body[0][0] if body else "(空)"

l1 = first(); time.sleep(14); l2 = first(); time.sleep(14); l3 = first()
print("自动翻页:", (l1 != l2) or (l2 != l3), "|", l1[:10], l2[:10], l3[:10])
client.close()
