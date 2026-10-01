"""确认阅读任务链成功版本（那次 SUCCESS 是 60s 计时链修复后? 不——
proc_d8ebcec3eaf9 是「接链后首轮」：当时链=去阅读→开书→SUCCESS，
WaitOneMinute 还没接。这次退出通知只是旧进程收尾，无新信息。
真正要补的是赠币入账读数。现在直接抓奖励页赠币数值。"""
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
boxes = client.recognize("OCR", {}, s).text_boxes()
print("=== 当前页 OCR ===")
for t, b in sorted(boxes, key=lambda x: x[1][1])[:12]:
    print(f"y={b[1]:4d} | {t}")
# 赠币数值
import re
for t, b in boxes:
    m = re.search(r"今日已获赠币\s*(\d+)", t)
    if m:
        print(f">>> 今日已获赠币 = {m.group(1)}")
client.close()
