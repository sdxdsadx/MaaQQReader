"""点入口后页面几乎空白（只有时间）——奖励页加载中或跳转失败白屏。
等 5 秒重新 OCR；若仍白屏，重启 app 再来（奖励页白屏偶发，重启即好）。"""
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
time.sleep(5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
print(f"OCR {len(boxes)} 条:")
for t, b in sorted(boxes, key=lambda x: x[1][1])[:12]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
