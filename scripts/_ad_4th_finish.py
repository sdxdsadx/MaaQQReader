"""第 4 条是「观看30秒，可获得奖励」游戏型广告（负重/背包 UI = 游戏），
X 在 (34,58)。等 30 秒倒计时 → 找领取 → 若弹「继续观看/放弃奖励」处理。
这类游戏广告有时要点击游戏画面元素——先等。"""
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


time.sleep(32)
boxes = ocr()
j = " ".join(t for t, b in boxes)
print("30s后:", j[:130], flush=True)

claim = [(t, b) for t, b in boxes if "领取" in t or "去领取" in t]
print("领取按钮:", claim, flush=True)
for t, b in claim[:1]:
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
    boxes = ocr()
    j = " ".join(t for t, b in boxes)
    print("领取后:", j[:110], flush=True)
    break

# 逐层退出到奖励页
for i in range(5):
    boxes = ocr()
    if on_reward(boxes):
        break
    xbtn = [(t, b) for t, b in boxes if t.strip() in ("X", "×", "x") and b[1] < 300]
    if xbtn:
        t, b = xbtn[0]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    else:
        client.swipe(360, 640, 360, 640, 0)
    time.sleep(2.5)

boxes = ocr()
j = " ".join(t for t, b in boxes)
cap = ("安全验证" in j) or ("滑块" in j) or ("拼图" in j)
print("回奖励页:", on_reward(boxes), flush=True)
print("验证码:", cap, flush=True)
print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
print("赠币:", [t for t, b in boxes if "已获赠币" in t], flush=True)

if cap:
    import subprocess
    r = subprocess.run(
        [r"D:\python\python.exe", r"G:\project_X\scripts\live_captcha_auto.py"],
        cwd=r"G:\project_X", capture_output=True, text=True, timeout=150, errors="replace")
    print(r.stdout[-400:], flush=True)
    boxes = ocr()
    j = " ".join(t for t, b in boxes)
    cap2 = ("安全验证" in j) or ("滑块" in j) or ("拼图" in j)
    print("求解后验证码:", cap2, flush=True)
    print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
client.close()
