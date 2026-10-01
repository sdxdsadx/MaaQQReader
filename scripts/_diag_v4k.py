"""完整导航确认: 点击书架页「再读10分钟领20赠币>」→ 应进奖励页（看小视频领好礼）。
box=(55,193,208,27) 中心≈(159,206)。点完 3 秒截图 OCR 验证。"""
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
client.swipe(159, 206, 159, 206, 80)
time.sleep(3.5)
s = client.screencap()
ocr = client.recognize("OCR", {}, s)
boxes = ocr.text_boxes()
print("=== 点击入口后的页面（含 奖/赠币/视频/游戏/礼物）===")
for t, b in boxes:
    if any(k in t for k in ("奖", "赠币", "视频", "游戏", "礼物", "福利")):
        print(f"box={b} | {t}")
client.close()
