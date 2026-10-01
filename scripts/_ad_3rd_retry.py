"""「观看11秒可获得奖励」还在（秒数可能重置或这是浏览类）。
这类广告模式：点击广告内容区域触发跳转浏览 11 秒 → 回来领奖。
或者要等它自动倒计时。策略：再等 15s → 截屏 → 若还卡着，找 X 退出放弃，
继续第 4 条（实测多数能过，个别类型放弃不损失——昨天验证提前发奖机制）。"""
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
j = " ".join(t for t, b in boxes)
print("15s后:", j[:110], flush=True)

if not on_reward(boxes):
    # 尝试点「观看11秒可获得奖励」文字本身（有的广告要点它开始计时）
    watch = [(t, b) for t, b in boxes if "观看" in t and "秒" in t]
    if watch:
        t, b = watch[0]
        x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
        print(f"点 {t} @ ({x},{y})", flush=True)
        client.swipe(x, y, x, y, 60)
        time.sleep(14)
        boxes = ocr()
        j2 = " ".join(t for t, b in boxes)
        print("观看后:", j2[:110], flush=True)

# 逐层退出到奖励页
for i in range(5):
    boxes = ocr()
    if on_reward(boxes):
        break
    xbtn = [(t, b) for t, b in boxes if t.strip() in ("X", "×", "x") and b[1] < 500]
    if xbtn:
        t, b = xbtn[0]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    else:
        client.swipe(360, 640, 360, 640, 0)
    time.sleep(2.5)

boxes = ocr()
claim = [(t, b) for t, b in boxes if "领取奖励" in t or "去领取" in t]
for t, b in claim[:1]:
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
    boxes = ocr()

print("回奖励页:", on_reward(boxes), flush=True)
print("验证码:", has_captcha(boxes), flush=True)
print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
client.close()
