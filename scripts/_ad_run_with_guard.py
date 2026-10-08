"""单广告+守护验证：跑一条广告，结束后 _captcha_guard.check_and_solve，
反复至 12/12 或无入口。同时统计验证码出现率。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import _captcha_guard as guard
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


def progress(boxes):
    for t, b in boxes:
        if "每看完1次" in t:
            return t
    return "?"


def find_watch():
    for _ in range(8):
        boxes = ocr()
        w = [(t, b) for t, b in boxes if "立即观看" in t]
        if w:
            return w[0]
        client.swipe(360, 1150, 360, 400, 500)
        time.sleep(1.6)
    return None


def back_to_reward():
    for i in range(6):
        boxes = ocr()
        if on_reward(boxes):
            return True
        giveup = [(t, b) for t, b in boxes if "放弃奖励" in t]
        xbtn = [(t, b) for t, b in boxes if t.strip() in ("X", "×", "x") and b[1] < 400]
        if giveup:
            t, b = giveup[0]
            client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
            time.sleep(2.5)
            continue
        if xbtn:
            t, b = xbtn[0]
            client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        else:
            client.swipe(360, 640, 360, 640, 0)
        time.sleep(2.2)
    return on_reward(ocr())


print("起始:", progress(ocr()), flush=True)
for ad_no in range(1, 15):
    boxes = ocr()
    prog = progress(boxes)
    if "12/12" in prog:
        print("🎉 12/12 达成", flush=True)
        break
    print(f"--- 第 {ad_no} 轮 ({prog}) ---", flush=True)
    watch = find_watch()
    if not watch:
        print("无入口，停", flush=True)
        break
    t, b = watch
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(35)

    for i in range(10):
        boxes = ocr()
        j = " ".join(t for t, b in boxes)
        if on_reward(boxes):
            break
        if "已发放" in j:
            time.sleep(2)
            break
        if "放弃奖励" in j and "继续观看" in j:
            cont = [(t, b) for t, b in boxes if "继续观看" in t]
            give = [(t, b) for t, b in boxes if "放弃奖励" in t]
            if i < 2 and cont:
                t, b = cont[0]
                client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
                time.sleep(32)
                continue
            if give:
                t, b = give[0]
                client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
                time.sleep(2.5)
                continue
        if any(k in j for k in ("直播", "需要下滑", "上滑", "浏览")):
            client.swipe(360, 900, 360, 300, 400)
            time.sleep(7)
            continue
        claim = [(t, b) for t, b in boxes if "领取奖励" in t or "去领取" in t]
        if claim:
            t, b = claim[0]
            client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
            time.sleep(3)
            continue
        time.sleep(6)

    ok = back_to_reward()
    cleared = guard.check_and_solve(client)
    boxes = ocr()
    print(f"轮次完成: 回页={ok} 验证码清={cleared} {progress(boxes)}", flush=True)
    time.sleep(3)

print("最终:", progress(ocr()), flush=True)
client.close()
