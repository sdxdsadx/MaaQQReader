"""第 2 条广告跑完：回奖励页 ✅ 无验证码 ✅ 但进度仍 1/12（没涨！）——
第 2 条广告可能是没完成浏览要求（下滑不够）或点 X 太早放弃了奖励。
第一轮「奖励已发放」说明第 1 条计入了。
继续第 3 条，这次：浏览下滑 5 次（多一次），确认「奖励已发放」出现再退出。"""
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


def reward_granted(boxes):
    j = " ".join(t for t, b in boxes)
    return "奖励已发放" in j or "已发放" in j


def has_captcha(boxes):
    j = " ".join(t for t, b in boxes)
    return ("安全验证" in j) or ("滑块" in j) or ("拼图" in j)


# 滚动到入口
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
print("已点立即观看(第3条)", flush=True)

# 等倒计时走完（轮询到秒数<=5 或 45s）
time.sleep(30)
# 上滑浏览直到「奖励已发放」出现（最多 6 次）
granted = False
for i in range(6):
    boxes = ocr()
    if on_reward(boxes):
        break
    if reward_granted(boxes):
        granted = True
        print("🎉 奖励已发放", flush=True)
        time.sleep(2)
        break
    client.swipe(360, 900, 360, 300, 400)
    print(f"上滑{i+1}", flush=True)
    time.sleep(7)

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
