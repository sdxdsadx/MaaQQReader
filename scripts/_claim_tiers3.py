"""好消息：书架页顶部显示「15分钟」——今日有效阅读已达 15 分钟！
（10 分钟档达标）「时长兑赠币，立即领取>」入口在 y=194。
点它进奖励页领 10 分钟档 + 30 分钟档（30 分钟档可能还差）+ 检查听书。"""
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
# 10分钟档领取 (198,1176) / 30分钟档 (484,1176)
client.swipe(216, 1189, 216, 1189, 60); time.sleep(2.5)
print("10分钟档后:", coins(), flush=True)
client.swipe(502, 1189, 502, 1189, 60); time.sleep(2.5)
print("30分钟档后:", coins(), flush=True)
client.close()
