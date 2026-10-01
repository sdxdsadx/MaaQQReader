"""auto_read 的呼菜单点击把页面点进了「书友榜」（粉丝值/支持/总榜月榜）——
坐标适配的是昨天那本书的正文页，今天这本书 UI 略不同（正文页顶部有
章评区入口），点中央呼出的是章评/打赏面板。
需要重新校准 auto_read 的交互坐标。先回到正文页：
BACK 两次 → 重新点第1章 → 呼菜单用点击后 OCR 验证「设置」可见性再继续。
简化：当前先 BACK 回正文，再手动点中央呼菜单，OCR 找「设置」的真实位置。"""
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
client.swipe(360, 640, 360, 640, 0)
time.sleep(2)
client.swipe(360, 640, 360, 640, 0)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
texts = [t for t, b in boxes]
print("BACK×2后:", " | ".join(texts[:8])[:140], flush=True)
# 呼菜单
client.swipe(360, 640, 360, 640, 60)
time.sleep(1.8)
s2 = client.screencap()
menu = [(t, b) for t, b in client.recognize("OCR", {}, s2).text_boxes()
        if any(k in t for k in ("设置", "目录", "进度", "书评区", "自动阅读"))]
print("菜单项:", menu, flush=True)
client.close()
