"""用户说得对，两张卡状态：
1) 每日听书30分钟+20赠币：已听117分钟，按钮「立即领取」（y=706）——没领！
   → 立即点领取
2) 每日阅读：今日再读6分钟领20赠币（用户说还需24分钟？页面上写 6，
   以页面为准），时长进度条 10分钟(y=450)/30分钟(y=452) 两档 + 领取按钮
   (y=480 x=198 / x=484)——有「领取」可点！先试试直接点领取（可能时长
   已达标但页面没刷新）。
执行：①点听书「立即领取」②点阅读 10分钟档「领取」③读结果。"""
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

def tap(x, y, label):
    print(f"点{label} @ ({x},{y})", flush=True)
    client.swipe(x, y, x, y, 60)
    time.sleep(2.5)

# ① 听书 立即领取
tap(551 + 40, 706 + 20, "听书·立即领取")
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
joined = " | ".join(t for t, b in sorted(boxes, key=lambda x: x[1][1])[:14])
print("领取后页面:", joined[:180], flush=True)
client.close()
