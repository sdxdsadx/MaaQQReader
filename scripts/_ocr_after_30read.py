"""30 分钟自动阅读挂机完成（11:48→12:19，含多次重新开启，实际覆盖
30 分钟窗口）。现在去奖励中心：
①找「你已阅读30分钟」相关弹窗先确认没有残留
②到奖励页找阅读卡：「今日再读0分钟领20赠币」应已达标（自动发 or 需领取）
③领两个相邻代币奖励（+20 每日阅读 / +20 阅读时长档位）共 40
先 OCR 奖励页顶部。"""
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
for t, b in sorted(boxes, key=lambda x: x[1][1])[:18]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
