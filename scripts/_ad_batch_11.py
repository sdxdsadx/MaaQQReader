"""批量跑剩余 11 条广告：循环单广告处理（用今天验证过的全类型处理逻辑），
每条完成后检查验证码。直播型/浏览型/倒计时型走完整流程，拉活型（快手/
游戏跳第三方）识别后直接放弃（继续观看→等待→放弃奖励）。
策略要点（今日实测沉淀）：
- 直播/浏览型：上滑 4-6 次，等「奖励已发放」再退
- 倒计时视频型：等秒数走完→领取
- 拉活型（出现 跳转详情页或第三方应用 + 无领取按钮）：X→放弃奖励
- 每轮结束回奖励页必查验证码"""
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


def progress(boxes):
    for t, b in boxes:
        if "每看完1次" in t:
            return t
    return "?"


def solve_captcha():
    import subprocess
    r = subprocess.run(
        [r"D:\python\python.exe", r"G:\project_X\scripts\live_captcha_auto.py"],
        cwd=r"G:\project_X", capture_output=True, text=True, timeout=150, errors="replace")
    tail = r.stdout[-250:] if r.stdout else ""
    print("  求解:", tail.replace(chr(10), " | ")[-200:], flush=True)
    time.sleep(2)


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
        xbtn = [(t, b) for t, b in boxes if t.strip() in ("X", "×", "x") and b[1] < 400]
        giveup = [(t, b) for t, b in boxes if "放弃奖励" in t]
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


TARGET = 12
results = []

for ad_no in range(2, 13):
    boxes = ocr()
    prog = progress(boxes)
    done = f"{TARGET}/{TARGET}" in prog
    print(f"===== 第 {ad_no} 条（当前 {prog}）=====", flush=True)
    if done:
        print("已达 12/12，提前收工", flush=True)
        break

    watch = find_watch()
    if not watch:
        print("❌ 找不到立即观看，跳过本轮", flush=True)
        results.append((ad_no, "NO_ENTRY"))
        continue
    t, b = watch
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(35)

    granted = False
    abandoned = False
    for i in range(10):
        boxes = ocr()
        j = " ".join(t for t, b in boxes)
        if on_reward(boxes):
            granted = "already"
            break
        if "已发放" in j:
            granted = True
            time.sleep(2)
            break
        if "放弃奖励" in j and "继续观看" in j:
            # 拉活型：等待一次继续观看（可能倒计时自动完成），否则放弃
            cont = [(t, b) for t, b in boxes if "继续观看" in t]
            give = [(t, b) for t, b in boxes if "放弃奖励" in t]
            if i < 2 and cont:
                t, b = cont[0]
                client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
                print("  继续观看", flush=True)
                time.sleep(32)
                continue
            if give:
                t, b = give[0]
                client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
                print("  放弃奖励（拉活型）", flush=True)
                abandoned = True
                time.sleep(2.5)
                continue
        if ("直播" in j) or ("需要下滑" in j) or ("上滑" in j) or ("浏览" in j):
            client.swipe(360, 900, 360, 300, 400)
            print(f"  上滑{i+1}", flush=True)
            time.sleep(7)
            continue
        claim = [(t, b) for t, b in boxes if "领取奖励" in t or "去领取" in t]
        if claim:
            t, b = claim[0]
            client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
            print("  领取", flush=True)
            time.sleep(3)
            continue
        time.sleep(6)

    ok = back_to_reward()
    boxes = ocr()
    cap = has_captcha(boxes)
    if cap:
        print("  ⚠ 验证码出现 → 求解", flush=True)
        solve_captcha()
        cap = has_captcha(ocr())
    verdict = ("GRANTED" if granted is True else
               "ALREADY" if granted == "already" else
               "ABANDONED" if abandoned else "UNKNOWN")
    print(f"  结果: {verdict} | 验证码: {cap} | 进度: {progress(ocr())}", flush=True)
    results.append((ad_no, verdict, "CAPTCHA" if cap else ""))
    time.sleep(3)

print("\n===== 批量完成 =====")
for r_ in results:
    print(r_)
print("最终进度:", progress(ocr()), flush=True)
coins = [t for t, b in ocr() if "已获赠币" in t]
print("赠币:", coins, flush=True)
client.close()
