"""静默=没找到入口或异常。抓全页 OCR 落盘判断。"""
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
boxes = client.recognize("OCR", {}, s).text_boxes()
print("OCR 条数:", len(boxes), flush=True)
for t, b in sorted(boxes, key=lambda x: x[1][1])[:14]:
    print(f"y={b[1]:4d} | {t}", flush=True)
# 不管在哪，先点「时长兑赠币」或「书架」入口尝试进奖励页
entered = False
for t, b in boxes:
    if "时长兑赠币" in t:
        x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
        client.swipe(x, y, x, y, 80)
        entered = True
        print("点: 时长兑赠币", flush=True)
        break
if not entered:
    for t, b in boxes:
        if t.strip() == "书架" and b[1] > 1100:
            client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 80)
            time.sleep(2)
            s2 = client.screencap()
            for t2, b2 in client.recognize("OCR", {}, s2).text_boxes():
                if "时长兑赠币" in t2:
                    client.swipe(b2[0] + b2[2] // 2, b2[1] + b2[3] // 2,
                                 b2[0] + b2[2] // 2, b2[1] + b2[3] // 2, 80)
                    entered = True
                    print("点书架后→时长兑赠币", flush=True)
                    break
            break
time.sleep(3)
client.swipe(360, 1000, 360, 550, 500)
time.sleep(2)
s3 = client.screencap()
print("=== 奖励页状态 ===", flush=True)
for t, b in sorted(client.recognize("OCR", {}, s3).text_boxes(), key=lambda x: x[1][1]):
    if any(k in t for k in ("已获赠币", "再读", "已读", "领取", "分钟")):
        print(f"y={b[1]:4d} | {t}", flush=True)
client.close()
