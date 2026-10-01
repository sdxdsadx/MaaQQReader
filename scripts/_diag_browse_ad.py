"""live_texts 已含「去体验」→ is_live=True → _handle_live_ad 应该生效了，
但仍卡 167+ observe 同页——为什么？看 _handle_live_ad：swipes>=8 后
live_exit_action=tap_point(55,118) 左上角 X，然后 press_back。
可能卡在：_handle_live_ad 的 Action.wait(5s) 和 swipe 被执行但
「滚动 5s 下滑」在浏览型广告里不翻页（内容短），而 X 在左上角 y=118 但
该广告的 X 位置不同？当前页 OCR: '小','广告','反馈'——「反馈」在右上，
X 可能在 y≈150。且 observe 一直出「去体验9秒」——秒数不变？

先活体看当前页面布局：截屏 OCR 全部 + 找 X/关闭元素坐标。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
print("=== 当前页（浏览广告）===")
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]} | {t}")
client.close()
