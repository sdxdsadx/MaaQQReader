"""「观看11秒」点击无效——这条广告类型（快手极速版拉活）必须跳第三方
才能完成，属于昨天确认过的「无法静默完成」类型。放弃该条，BACK 退出，
继续第 4 条广告。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

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


# BACK 退出放弃
for _ in range(3):
    subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=15)
    time.sleep(2)
    boxes = ocr()
    if on_reward(boxes):
        break

boxes = ocr()
print("放弃第3条后回奖励页:", on_reward(boxes), flush=True)

# 第 4 条
watch = None
for _ in range(4):
    boxes = ocr()
    w = [(t, b) for t, b in boxes if "立即观看" in t]
    if w:
        watch = w[0]
        break
    client.swipe(360, 1100, 360, 500, 500)
    time.sleep(1.8)
if not watch:
    sys.exit("找不到立即观看")

t, b = watch
client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
print("已点立即观看(第4条)", flush=True)

time.sleep(35)
granted = False
for i in range(5):
    boxes = ocr()
    if on_reward(boxes):
        break
    j = " ".join(t for t, b in boxes)
    if "已发放" in j:
        granted = True
        print("奖励已发放", flush=True)
        time.sleep(2)
        break
    if "直播" in j or "需要下滑" in j or "上滑" in j:
        client.swipe(360, 900, 360, 300, 400)
        print(f"上滑{i+1}", flush=True)
        time.sleep(7)
    else:
        time.sleep(6)

boxes = ocr()
if not on_reward(boxes):
    xbtn = [(t, b) for t, b in boxes if t.strip() in ("X", "×", "x") and b[1] < 400]
    if xbtn:
        t, b = xbtn[0]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(3)
    else:
        client.swipe(360, 640, 360, 640, 0)
        time.sleep(3)

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
