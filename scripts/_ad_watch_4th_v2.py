"""回书架成功。现在用今天学到的完整知识跑第 4 条广告：
- 直播型：上滑 4-5 次等「奖励已发放」→ X 退出
- 拉活型（快手类）：点「观看N秒」→ 若弹「继续观看/放弃奖励」选继续观看等 30s → 领取
- 完成后回奖励页必查验证码（今日已实证 1 次滑动验证，求解器 1 轮 SOLVED）"""
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


# 回奖励页：点「本周阅读时长/领赠币>」入口
boxes = ocr()
entry = [(t, b) for t, b in boxes if "领赠币" in t and b[1] < 300]
if entry:
    t, b = entry[0]
    client.swipe(b[0] + 100, b[1] + 10, b[0] + 100, b[1] + 10, 60)
    time.sleep(3)

# 滚动到立即观看
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
    print("进度:", [t for t, b in ocr() if "每看完1次" in t], flush=True)
    sys.exit("找不到立即观看")

t, b = watch
client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
print("已点立即观看(第4条)", flush=True)
time.sleep(35)

# 通用处理循环：最多 8 次动作
done = False
for i in range(8):
    boxes = ocr()
    j = " ".join(t for t, b in boxes)
    if on_reward(boxes):
        done = True
        print("回奖励页", flush=True)
        break
    if "已发放" in j:
        print("奖励已发放", flush=True)
        time.sleep(2)
        done = True
        break
    if "放弃奖励" in j and "继续观看" in j:
        cont = [(t, b) for t, b in boxes if "继续观看" in t]
        if cont:
            t, b = cont[0]
            client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
            print("继续观看", flush=True)
            time.sleep(30)
            continue
    if "直播" in j or "需要下滑" in j or "上滑" in j or "浏览" in j:
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
print("验证码:", has_captcha(boxes), flush=True)
print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
client.close()
