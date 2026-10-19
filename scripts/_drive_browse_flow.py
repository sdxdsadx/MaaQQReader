"""分支代码在。手动活体驱动完整流程：
①点跳过(684,24) → ②弹窗点「去领取奖励」→ ③看进度/回奖励页。
同时检查「去领取奖励」按钮坐标。"""
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

# ① 跳过
client.swipe(684, 24, 684, 24, 60)
time.sleep(2.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
print("① 跳过后:", " | ".join(t for t, b in boxes[:10])[:150])

# ② 去领取奖励
claim = None
for t, b in boxes:
    if "去领取奖励" in t:
        claim = b
        break
if claim:
    x, y = claim[0] + claim[2] // 2, claim[1] + claim[3] // 2
    print(f"② 点去领取奖励 @ ({x},{y})")
    client.swipe(x, y, x, y, 60)
    time.sleep(3)
else:
    print("② 无去领取按钮")

# ③ 当前状态
s2 = client.screencap()
texts2 = client.recognize("OCR", {}, s2).all_texts()
print("③ 现在:", " | ".join(texts2[:10])[:160])
client.close()
