"""SUCCESS！链路完整：AlreadyInBook(识别正文页) → WaitOneMinute(60s) →
ExitAfterTimer(退出回书架)。当前页=书架页（y=44 书架, y=138 600分钟）。
验收: 回奖励页看「今日已获赠币」是否从 204 增长（阅读满1分钟 +20）。"""
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
# 书架页 → 奖励页入口（再读N分钟领20赠币> 在 y≈193）
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
entry = None
for t, b in boxes:
    if "分钟领" in t or "阅读时长" in t:
        entry = b
        break
if entry:
    x, y = entry[0] + entry[2] // 2, entry[1] + entry[3] // 2
    print(f"点奖励入口 {t} @ ({x},{y})")
    client.swipe(x, y, x, y, 80)
    time.sleep(3)
s2 = client.screencap()
texts2 = client.recognize("OCR", {}, s2).text_boxes()
for t, b in sorted(texts2, key=lambda x: x[1][1])[:8]:
    print(f"y={b[1]:4d} | {t}")
client.close()
