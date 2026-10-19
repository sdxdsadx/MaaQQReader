"""好消息：重启+点书后直接进了第1章正文（y=724 有正版授权提示条 = 正文页顶部）。
现在正文页就绪。呼菜单并 OCR 全部菜单项（不再用固定坐标，现场校准）。"""
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
client.swipe(360, 640, 360, 640, 60)
time.sleep(1.8)
s = client.screencap()
menu = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
        if any(k in t for k in ("设置", "目录", "进度", "书评区", "自动阅读", "护眼", "更多设置"))]
print("菜单项:", menu, flush=True)
client.close()
