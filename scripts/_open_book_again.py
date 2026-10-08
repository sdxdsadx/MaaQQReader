"""本周阅读时长 155 分钟（还在涨，说明有计时的活动在进行）。
全职法师显示「正在播放第348章」——听书还在播！
点书名进正文，然后立刻处理：暂停听书播放（听书面板 II 按钮）→
正文页开自动阅读。若 toast 说人声朗读中 → 重启 app 清会话 → 再来。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
qz = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "全职法师" in t]
t, b = qz[0]
client.swipe(b[0] + 50, b[1] + 15, b[0] + 50, b[1] + 15, 60)
time.sleep(4)
s2 = client.screencap()
texts = client.recognize("OCR", {}, s2).all_texts()
print("点后:", " | ".join(texts[:6])[:120], flush=True)
client.close()
