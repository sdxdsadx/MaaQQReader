"""已进奖励页！今日已获赠币 80（今天新周期，自动签到+80）。
当前状态：
- 每日阅读领赠币：今日再读10分钟领20赠币（阅读还没跑——今天阅读任务没完成）
- 阅读时长档：10分钟档(y=1176 x=198 领取) / 30分钟档(x=484 领取)——
  昨天已读 640 分钟，今天 0——但档位是"今日阅读时长"？昨天显示领过。
  先试点两个领取看是否可领（可能今天时长还不足）
- 听书卡在下方（往下翻找「每日听书30分钟+20赠币 已听N分钟」）
先点两个领取，再下滑找听书卡领取。"""
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

def coins():
    s = client.screencap()
    for t, b in client.recognize("OCR", {}, s).text_boxes():
        if "今日已获赠币" in t:
            return t
    return "?"

def tap(x, y, label):
    client.swipe(x, y, x, y, 60)
    time.sleep(2.5)
    print(f"{label}: {coins()}", flush=True)

tap(216, 1189, "10分钟档领取")
tap(502, 1189, "30分钟档领取")
client.close()
