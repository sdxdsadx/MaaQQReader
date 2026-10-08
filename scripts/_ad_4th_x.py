"""第 4 条是「超自然行动组」游戏拉活广告（「跳转详情页或第三方应用」），
倒计时结束但无领取按钮——又是需要跳第三方的类型（或需要点 X 出
「继续观看/放弃奖励」对话框）。X 在 (34,58)。点 X 看对话框。"""
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


client.swipe(53, 77, 53, 77, 60)
time.sleep(2.5)
boxes = ocr()
j = " ".join(t for t, b in boxes)
print("点X后:", j[:150], flush=True)

# 若有对话框按钮
cont = [(t, b) for t, b in boxes if "继续观看" in t]
giveup = [(t, b) for t, b in boxes if "放弃奖励" in t]
claim = [(t, b) for t, b in boxes if "去领取" in t or "领取奖励" in t]
print("继续观看:", bool(cont), "| 放弃:", bool(giveup), "| 领取:", claim, flush=True)

if claim:
    t, b = claim[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
elif cont:
    t, b = cont[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    print("选继续观看——等30s", flush=True)
    time.sleep(32)
    boxes = ocr()
    claim2 = [(t, b) for t, b in boxes if "去领取" in t or "领取奖励" in t or "立即领取" in t]
    if claim2:
        t, b = claim2[0]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(3)

boxes = ocr()
j = " ".join(t for t, b in boxes)
cap = ("安全验证" in j) or ("滑块" in j) or ("拼图" in j)
print("回奖励页:", on_reward(boxes), flush=True)
print("验证码:", cap, flush=True)
print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
print("赠币:", [t for t, b in boxes if "已获赠币" in t], flush=True)
client.close()
