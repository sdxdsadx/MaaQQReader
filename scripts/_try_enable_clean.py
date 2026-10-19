"""浮窗没了（BACK x2 可能已把听书会话退掉，或浮窗暂时隐藏）。
直接试开自动阅读（幂等菜单→设置→自动阅读），若再出
「人声朗读中无法开启自动阅读模式」toast 说明会话还挂着；
若成功开起来 → 翻页验证。写综合测试。"""
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
            if any(k in t for k in ("设置", "自动阅读", "更多", "朗读", "无法"))]

# 幂等呼菜单
for _ in range(2):
    client.swipe(360, 640, 360, 640, 60); time.sleep(1.5)
    if "设置" in " ".join(marks()):
        break
client.swipe(452, 1247, 452, 1247, 60); time.sleep(1.5)
print("设置面板:", marks(), flush=True)
client.swipe(355, 1122, 355, 1122, 60); time.sleep(1.5)
m = marks()
print("点自动阅读后:", m, flush=True)
client.swipe(360, 640, 360, 640, 0); time.sleep(1.5)

def first():
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    body = [(t, b) for t, b in boxes if 100 < b[1] < 1000 and b[0] < 600 and b[2] > 40]
    body.sort(key=lambda x: x[1][1])
    return body[0][0] if body else "(空)"

l1 = first(); time.sleep(14); l2 = first(); time.sleep(14); l3 = first()
print("L1:", l1[:18]); print("L2:", l2[:18]); print("L3:", l3[:18])
print("自动翻页:", (l1 != l2) or (l2 != l3))
client.close()
