"""赠币 204 未涨（204=看广告后的值；+20 阅读奖励需要「领取」动作或已入账
但页面显示的是总池）。注意：奖励页「今日再读9分钟领20赠币」是**时长兑赠币**
模式——需要读满 10 分钟才可领，1 分钟挂机只是阅读时长累计，不直接发币。
而且刚刚那次成功链是 AlreadyInBook→60s→Exit，书页阅读 1 分钟是否计入
「再读9分钟」进度待确认。

关键判读：页首「今日已获赠币 204」没变——阅读任务的 20 币要「今日再读
N分钟领20赠币」达标后**手动领取**或自动发？看奖励页中部「今日再读9分钟
领20赠币」当前状态（是否变为可领取）。滑到中部读。"""
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
client.swipe(360, 1000, 360, 500, 500)
time.sleep(2)
s = client.screencap()
for t, b in sorted(client.recognize("OCR", {}, s).text_boxes(), key=lambda x: x[1][1])[:16]:
    print(f"y={b[1]:4d} | {t}")
client.close()
