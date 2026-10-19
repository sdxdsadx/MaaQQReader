"""选了继续观看后又在游戏页（负重/背包 UI）——这个超自然行动组广告要求
真的跳进游戏画面 30 秒，模拟器环境无法完成（需要真实游戏交互）。
放弃该条：点 X → 放弃奖励 → 回奖励页。然后评估今天广告成果并收尾。"""
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


def ocr():
    s = client.screencap()
    return client.recognize("OCR", {}, s).text_boxes()


def on_reward(boxes):
    j = " ".join(t for t, b in boxes)
    return ("已获赠币" in j) or ("看小视频领好礼" in j) or ("每看完1次" in j)


# X → 放弃奖励
client.swipe(53, 77, 53, 77, 60)
time.sleep(2.5)
boxes = ocr()
giveup = [(t, b) for t, b in boxes if "放弃奖励" in t]
if giveup:
    t, b = giveup[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
    print("已放弃", flush=True)

boxes = ocr()
if not on_reward(boxes):
    client.swipe(360, 640, 360, 640, 0)
    time.sleep(2.5)
    boxes = ocr()

j = " ".join(t for t, b in boxes)
cap = ("安全验证" in j) or ("滑块" in j) or ("拼图" in j)
print("回奖励页:", on_reward(boxes), flush=True)
print("验证码:", cap, flush=True)
print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
print("赠币:", [t for t, b in boxes if "已获赠币" in t], flush=True)
client.close()
