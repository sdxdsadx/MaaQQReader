"""重要：验证码求解器连续失败「连续 2 轮检测不到轨道 → 放弃，dist=0」——
live_captcha_auto.py 的 detect_slide 在这个新验证码变体上失效！
之前两次成功（dist=294/338）的验证码与现在不同。
当前奖励页 OCR 无「安全验证」字样但 CAPTCHA_ON=True——求解器视角的
CAPTCHA_ON 来自 detect=FOUND？日志显示 r1 detect=FOUND track 空 →
轨道区域截屏 OCR 匹配到了但几何检测失败。
活体验证：跑 detect_slide 看当前验证码状态与轨道/滑块位置。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.captcha.slide import detect_slide
from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
d = detect_slide(s)
print("detect_slide:", d)
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("安全", "滑块", "拼图", "验证")):
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}")
client.close()
