"""观察：这是**直播型广告**（进入直播间 + 需要下滑浏览更多才能领取奖励）
——60 秒都没自动结束，需要「上滑浏览」动作。旧 DailyAdFlow 的
_handle_live_ad 处理过这种（上滑 N 次后 X 退出）。
我的监督脚本需要补：直播广告处理逻辑（上滑 3-4 次 → 等待 → X 关闭）。
同时修复 screencap 截图 API 用法（client.screencap() 返回 Screenshot 对象，
PNG bytes 要用别的方法——看 maa factory 的接口）。
直接采用 DailyAdFlow 相同动作序列：上滑→等待→领取→X 退出→回奖励页。"""
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


# 当前还在直播广告页（上次脚本退出时未关）。直播处理：
# 上滑浏览 3 次（每次间隔 8s 满足浏览时长）→ 点 X 或 BACK
for i in range(4):
    boxes = ocr()
    if on_reward(boxes):
        break
    j = " ".join(t for t, b in boxes)
    print(f"滑动{i+1}: {j[:70]}", flush=True)
    client.swipe(360, 900, 360, 300, 400)  # 上滑
    time.sleep(8)

boxes = ocr()
if not on_reward(boxes):
    # 找 X 关闭（左上/右上）
    xbtn = [(t, b) for t, b in boxes if t.strip() in ("X", "×", "x") and b[1] < 400]
    print("X按钮:", xbtn, flush=True)
    if xbtn:
        t, b = xbtn[0]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(3)
    else:
        client.swipe(360, 640, 360, 640, 0)  # BACK
        time.sleep(3)

# 若出现「去领取奖励/立即领取」确认框则点领取
boxes = ocr()
claim = [(t, b) for t, b in boxes if "领取奖励" in t or "去领取" in t or "立即领取" in t]
print("领取按钮:", claim, flush=True)
for t, b in claim[:1]:
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)

boxes = ocr()
print("回奖励页:", on_reward(boxes), flush=True)
print("验证码检测:", has_captcha(boxes), flush=True)
print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
client.close()
