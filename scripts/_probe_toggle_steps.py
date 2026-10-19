"""确认：现在不在自动翻页（内容静止）——toggle 把它关了。
关键疑点：toggle 序列到底有没有点到「自动阅读」？之前 11:02 那次
成功过一次（L2≠L1 True），说明序列本身可用。现在页面在正文页，
重新跑 toggle 并在每一步后 OCR 确认（菜单有没有弹出、设置面板有没有
出现、点击后面板是否关闭）。写精细探针。"""
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

def snap(label):
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    marks = [t for t, b in boxes if any(k in t for k in ("设置", "目录", "自动阅读", "更多设置", "护眼"))]
    print(f"[{label}] {marks}", flush=True)

snap("初始")
client.swipe(360, 640, 360, 640, 60); time.sleep(1.5)
snap("呼菜单")
client.swipe(452, 1247, 452, 1247, 60); time.sleep(1.5)
snap("点设置")
client.swipe(355, 1122, 355, 1122, 60); time.sleep(1.5)
snap("点自动阅读")
client.swipe(360, 640, 360, 640, 0); time.sleep(1.5)
snap("收面板")
client.close()
