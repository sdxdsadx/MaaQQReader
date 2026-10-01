"""确认进度 1/12（第 3 条快手广告的 +1 生效了！），立即观看在 (553,222)。
跑第 4 条广告——完整监督含验证码检测。"""
import subprocess
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


client.swipe(593, 236, 593, 236, 60)
print("已点立即观看(第4条)", flush=True)
time.sleep(35)

done = False
for i in range(8):
    boxes = ocr()
    j = " ".join(t for t, b in boxes)
    if on_reward(boxes):
        done = True
        break
    if "已发放" in j:
        done = True
        print("奖励已发放", flush=True)
        time.sleep(2)
        break
    if "放弃奖励" in j and "继续观看" in j:
        cont = [(t, b) for t, b in boxes if "继续观看" in t]
        if cont:
            t, b = cont[0]
            client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
            print("继续观看", flush=True)
            time.sleep(30)
            continue
    if "直播" in j or "下滑" in j or "上滑" in j or "浏览" in j:
        client.swipe(360, 900, 360, 300, 400)
        print(f"上滑{i+1}", flush=True)
        time.sleep(7)
        continue
    claim = [(t, b) for t, b in boxes if "领取奖励" in t or "去领取" in t]
    if claim:
        t, b = claim[0]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        print("领取", flush=True)
        time.sleep(3)
        continue
    time.sleep(6)

boxes = ocr()
cap = has_captcha(boxes)
print("验证码:", cap, flush=True)
print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
if cap:
    print(">>> 求解验证码 <<<", flush=True)
    r = subprocess.run(
        [r"D:\python\python.exe", r"G:\project_X\scripts\live_captcha_auto.py"],
        cwd=r"G:\project_X", capture_output=True, text=True, timeout=150, errors="replace")
    print(r.stdout[-400:], flush=True)
    time.sleep(2)
    boxes = ocr()
    print("求解后验证码:", has_captcha(boxes), flush=True)
    print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
client.close()
