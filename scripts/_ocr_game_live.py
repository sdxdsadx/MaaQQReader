"""GameFlow 04:53 启动，20min 挂机 ≈ 05:15 结束。等的同时用独立日志看
GameFlow 实时输出（新 daily_all 还没重跑，当前这轮还是旧合并日志）。
活体 OCR 看游戏是否已进入挂机页（验证 Codex 的 GAME_CENTER 修复）。"""
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
for t, b in sorted(boxes, key=lambda x: x[1][1])[:10]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
