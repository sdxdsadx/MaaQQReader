"""点「去领取奖励」后回到广告页了！说明点按钮后它先回广告页要求看完 9 秒。
策略：等 9 秒倒计时结束再领。继续驱动：等 10s → 重新找「去领取奖励」→
若在广告页则再等，循环 3 次。"""
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
for attempt in range(4):
    time.sleep(10)
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    joined = " | ".join(t for t, b in boxes[:12])
    print(f"[{attempt}] 页面: {joined[:150]}", flush=True)
    claim = None
    for t, b in boxes:
        if "去领取奖励" in t:
            claim = b
            break
    if claim:
        x, y = claim[0] + claim[2] // 2, claim[1] + claim[3] // 2
        print(f"   点去领取奖励 @ ({x},{y})", flush=True)
        client.swipe(x, y, x, y, 60)
        time.sleep(3)
    if any("已获得" in t or "奖品" in t or "看小视频" in t for t, b in boxes):
        print("   检测到奖励/回奖励页特征，停", flush=True)
        break
client.close()
