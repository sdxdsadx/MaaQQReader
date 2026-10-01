"""听书 run_maa_ad 在跑但 MAA 无日志输出（旧 debug log 是 09-09 的）——
它的 MAA debug 目录用 --runtime G:\project_X\dev → dev\debug\maafw.log
但那也是昨天 21:53 的。结论：MAA tasker 已连接（ADB 预检过了）但 30 分钟
无 pipeline 动作。可能卡在 pipeline 等待识别（听书入口 OCR 不到）。
活体 OCR 看当前屏幕。"""
import sys
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
print(f"OCR {len(boxes)}:")
for t, b in sorted(boxes, key=lambda x: x[1][1])[:14]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
