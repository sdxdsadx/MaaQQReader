"""重要观察：#16 修复生效了——新逻辑 8 次下滑找「立即观看」都没找到，
**快速报可读错误退出**（不再死循环 40 分钟！这是修复的直接收益）。
但入口真找不到——OCR 显示当前页是「玩游戏领赠币/去玩游戏」游戏卡，
没有立即观看。今天 12/12 广告可能已完成？还是入口在别处？
看完整奖励页 OCR（找「看小视频领好礼」区）。"""
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
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("看小视频", "礼物", "观看", "视频", "广告", "每看完")):
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
