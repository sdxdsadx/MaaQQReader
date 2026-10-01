"""阅读任务 SUCCESS（3000）！且这次 run_task 在 MAA 结束后**正常退出**
（无挂死）——issue #13 修复①实机验证通过。
现在去奖励页领取：阅读 10分钟档+30分钟档（今天 35 分钟挂机已达标）+
检查听书 30 分钟档（13:14-13:45 挂机应已达标）+ 每日阅读 20 赠币。"""
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
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("已获赠币", "再读", "已读", "听书", "领取", "分钟")):
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
