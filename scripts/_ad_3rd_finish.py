"""第 3 条是「观看11秒可获得奖励」的倒计时广告（快手极速版）——
等 12 秒倒计时结束 → 点「去领取奖励」确认框（之前见过）→ 或等它自动跳转。
处理：等 15s → OCR 找 领取/确认 → 逐层退出回奖励页。"""
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


def has_captcha(boxes):
    j = " ".join(t for t, b in boxes)
    return ("安全验证" in j) or ("滑块" in j) or ("拼图" in j)


time.sleep(15)
boxes = ocr()
print("倒计时后:", " | ".join(t for t, b in boxes[:8])[:130], flush=True)

claim = [(t, b) for t, b in boxes if "领取" in t or "去领取" in t or "确定" in t]
print("领取类按钮:", claim, flush=True)
for t, b in claim[:1]:
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
    boxes = ocr()

for i in range(4):
    if on_reward(boxes):
        break
    client.swipe(360, 640, 360, 640, 0)
    time.sleep(2.5)
    boxes = ocr()

print("回奖励页:", on_reward(boxes), flush=True)
print("验证码:", has_captcha(boxes), flush=True)
print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
client.close()
