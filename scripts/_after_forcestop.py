"""重大发现：点击后弹出了「观看视频30秒，才能获得奖励 / 继续观看 / 放弃奖励」
——放弃奖励按钮出现了但我们已经 force-stop 了 app（对话框被杀）。
app 重启后落在开屏页（QQ阅读 海量原著想读就读）。
等开屏走完 → 跳过 → 回奖励页。关键知识：这类广告有「放弃奖励」出口按钮，
下次遇到直接点它优雅退出！"""
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
time.sleep(10)
s = client.screencap()
skip = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳过" in t]
if skip:
    t, b = skip[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
j = " ".join(t for t, b in boxes)
print("落地:", j[:110], flush=True)
print("在奖励页:", ("已获赠币" in j) or ("看小视频" in j), flush=True)
print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
client.close()
