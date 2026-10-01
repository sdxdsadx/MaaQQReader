"""daily_all 第二轮汇总：阅读✅ 听书❌(36s) 游戏✅ 广告❌(40min timeout)。
两个失败待查：
1) 听书 4000：单独重跑拿干净输出（现在没有别的任务占设备了）。
2) 广告 timeout：看这轮广告日志——GAME_HALL BACK 兜底生效了吗？
活体 OCR 看当前页面 + 读这轮广告日志。"""
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
