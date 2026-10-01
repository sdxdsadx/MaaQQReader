"""好消息：赠币 160→170（+10 = 第 3 条快手广告的奖励其实发放了！
「放弃奖励」对话框出现前奖励已算），且回到奖励页顶部。
第 4 条找不到立即观看——广告区还在更下方。下滑找并继续跑。"""
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

watch = None
for i in range(8):
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    w = [(t, b) for t, b in boxes if "立即观看" in t]
    if w:
        watch = w[0]
        print(f"[下滑{i}] 找到: {watch}", flush=True)
        break
    prog = [t for t, b in boxes if "每看完1次" in t]
    if prog:
        print("进度:", prog, flush=True)
    client.swipe(360, 1100, 360, 450, 500)
    time.sleep(1.8)
client.close()
