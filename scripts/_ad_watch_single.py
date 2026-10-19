"""找到「立即观看」(553,1066)，进度 0/12（今日广告从零开始）。
升级 _ad_watch_single.py：支持滚动定位+完整单广告监督循环（播放→回页→
截屏→验证码检测→求解→验证消失→确认进度+1）。跑第一条广告。"""
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

SHOT = Path(r"G:\project_X\runtime\screenshots\ad_watch")
SHOT.mkdir(parents=True, exist_ok=True)


def ocr():
    s = client.screencap()
    return client.recognize("OCR", {}, s).text_boxes()


def has_captcha(boxes):
    j = " ".join(t for t, b in boxes)
    return ("安全验证" in j) or ("滑块" in j) or ("拼图" in j)


def scroll_to_watch(max_swipes=4):
    for _ in range(max_swipes):
        boxes = ocr()
        w = [(t, b) for t, b in boxes if "立即观看" in t]
        if w:
            return w[0]
        client.swipe(360, 1100, 360, 500, 500)
        time.sleep(1.8)
    return None


# 回奖励页顶部再下滚（确保位置一致）
client.swipe(360, 500, 360, 1200, 500)
time.sleep(1.5)
watch = scroll_to_watch()
print("立即观看:", watch, flush=True)
if not watch:
    sys.exit("找不到入口")

t, b = watch
x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
client.swipe(x, y, x, y, 60)
print("已点立即观看", flush=True)

# 广告播放窗口：60s 内轮询，出现奖励页特征即结束
reward_seen = False
for i in range(12):
    time.sleep(5)
    boxes = ocr()
    j = " ".join(t for t, b in boxes)
    if "已获赠币" in j or "看小视频领好礼" in j:
        reward_seen = True
        print(f"[{i*5+5}s] 回到奖励页", flush=True)
        break
    print(f"[{i*5+5}s] 页面: {j[:80]}", flush=True)

time.sleep(2)
p = SHOT / "after_ad_1.png"
p.write_bytes(client.screencap())
boxes = ocr()
captcha = has_captcha(boxes)
print("验证码检测:", captcha, flush=True)
print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)

if captcha:
    print(">>> 检测到滑动验证，调用求解器 <<<", flush=True)
    import subprocess
    r = subprocess.run(
        [r"D:\python\python.exe", str(Path(r"G:\project_X\scripts\live_captcha_auto.py"))],
        cwd=str(Path(r"G:\project_X")), capture_output=True, text=True, timeout=120)
    print(r.stdout[-500:], flush=True)
    time.sleep(2)
    boxes2 = ocr()
    print("求解后验证码检测:", has_captcha(boxes2), flush=True)
    (SHOT / "after_solve_1.png").write_bytes(client.screencap())

client.close()
