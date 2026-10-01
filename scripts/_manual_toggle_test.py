"""过滤已生效（首行=正文了），但翻页验证仍 False——15s 内没翻页。
两种可能：①自动阅读根本没开成功（toggle 没点中）②自动阅读翻页速度
>15s/屏（对比昨日 11:02 成功那次，当时 L2 间隔 9s 就变了——那时是
呼菜单成功且点到开关）。
现在直接活体手动一步步来：看当前菜单/设置面板实际状态，手动点自动阅读，
然后 30s 内每 5s 读首行验证翻页速度。拿真数据。"""
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

def first():
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    body = [(t, b) for t, b in boxes if 100 < b[1] < 1000 and b[0] < 600 and b[2] > 40]
    body.sort(key=lambda x: x[1][1])
    return body[0][0] if body else "(空)"

def marks():
    s = client.screencap()
    return [t for t, b in client.recognize("OCR", {}, s).text_boxes()
            if any(k in t for k in ("设置", "自动阅读", "更多设置"))]

print("初始标记:", marks(), flush=True)
# 菜单当前态未知，先点中央呼出/收起
client.swipe(360, 640, 360, 640, 60); time.sleep(1.5)
m = marks()
print("点中央后:", m, flush=True)
if "设置" not in " ".join(m):
    client.swipe(360, 640, 360, 640, 60); time.sleep(1.5)
    print("再点中央后:", marks(), flush=True)
client.swipe(452, 1247, 452, 1247, 60); time.sleep(1.5)
print("点设置后:", marks(), flush=True)
client.swipe(355, 1122, 355, 1122, 60); time.sleep(1.5)
print("点自动阅读后:", marks(), flush=True)
client.swipe(360, 640, 360, 640, 0); time.sleep(1.5)
print("收面板后:", marks(), flush=True)
# 翻页速度采样：60s 内每 10s 读首行
lines = []
for i in range(6):
    lines.append(first())
    print(f"t={i*10}s: {lines[-1][:20]}", flush=True)
    time.sleep(10)
print("60s 内翻页次数:", sum(1 for i in range(1, len(lines)) if lines[i] != lines[i-1]))
client.close()
