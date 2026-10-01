"""10 屏下滑都没有「立即观看」和「明日再来」——奖励页滚动已到底，
「看小视频领好礼」整卡消失。可能：今日名额用完后卡片被移除（不留
「明日再来」文案），或卡片在页首（回顶看）。回顶部核对一次；
若真消失，则今日广告 12 条实际已完成（昨天 8 + 今天凌晨/上午 4），
failed 判定只是入口消失——修改期望即可。回顶部查证。"""
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
client.swipe(360, 400, 360, 1200, 400)
time.sleep(2)
client.swipe(360, 400, 360, 1200, 400)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
hits = [(t, b) for t, b in boxes
        if any(k in t for k in ("看小视频", "礼物", "观看", "视频领", "再来"))]
print("顶部相关行:", hits, flush=True)
for t, b in sorted(boxes, key=lambda x: x[1][1])[:14]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
