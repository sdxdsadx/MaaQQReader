"""出现「继续浏览/坚持退出」弹窗——点「坚持退出」离开。然后看是否回奖励页+进度。"""
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
s = client.screencap()
btn = None
for t, b in client.recognize("OCR", {}, s).text_boxes():
    if "坚持退出" in t:
        btn = b
        break
if btn:
    x, y = btn[0] + btn[2] // 2, btn[1] + btn[3] // 2
    print(f"点 坚持退出 ({x},{y})")
    client.swipe(x, y, x, y, 80)
time.sleep(4)
s2 = client.screencap()
texts = client.recognize("OCR", {}, s2).all_texts()
print("=== 退出后页面 ===")
for t in texts[:18]:
    print(t)
client.close()
