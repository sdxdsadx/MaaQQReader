"""🎉 300 分钟滑动阅读完成（taps=880，00:29→05:12）！
书架页显示今日阅读时长 **146 分钟**（远超 30 分钟档）！
立即去奖励页领取：30 分钟档 + 45 分钟档 + 更高档位全部可领。
（档位结构：10/30/45/60... 每 15 分钟一档 20 赠币递增？之前看到 10分钟
和30分钟两档，146 分钟应该能领好几档。）"""
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
client.swipe(165, 204, 165, 204, 60)
time.sleep(3)

def coins():
    s = client.screencap()
    for t, b in client.recognize("OCR", {}, s).text_boxes():
        if "今日已获赠币" in t:
            return t
    return "?"

print("进奖励页:", coins(), flush=True)
# 下滑到阅读档位区
client.swipe(360, 1050, 360, 500, 600)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("再读", "领取", "分钟", "已领取")):
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
