"""当前在书城 tab。切到「书架」tab（y=1250, x=89 中心），看书架页有没有
「本周阅读时长/再读N分钟领赠币」入口；再全页 OCR 确认奖励入口文案。"""
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
client.swipe(89, 1263, 89, 1263, 80)  # tap 书架 tab
time.sleep(2.5)
s = client.screencap()
ocr = client.recognize("OCR", {}, s)
boxes = ocr.text_boxes()
print("=== 书架页: 含 奖/赠币/阅读时长/福利/分钟 的文本 ===")
for t, b in boxes:
    if any(k in t for k in ("奖", "赠币", "时长", "福利", "分钟", "有奖")):
        print(f"box={b} | {t}")
print("=== 书架页前 20 条 ===")
for t, b in boxes[:20]:
    print(f"y={b[1]:4d} | {t}")
client.close()
