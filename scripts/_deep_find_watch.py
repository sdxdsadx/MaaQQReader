"""页面在游戏卡+抽奖区——「看小视频领好礼」卡不在当前视口。
8 次下滑应该能扫到……除非入口在页面**最底部**（需要下滑更多次）
或今天的入口文案变了（如「明日再来」=今日 12 个名额已用完！
昨天 8/12+今天若已看几条，可能名额耗尽——之前见过「明日再来」状态）。
下滑到底翻页验证。"""
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
for i in range(10):
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    j = " ".join(t for t, b in boxes)
    if "明日再来" in j and "看小视频" in j:
        print("⚠ 今日看视频名额已用完（明日再来）", flush=True)
        print([t for t, b in boxes if "看小视频" in t or "明日再来" in t], flush=True)
        break
    w = [(t, b) for t, b in boxes if "立即观看" in t]
    if w:
        print("找到入口:", w[0], flush=True)
        break
    client.swipe(360, 1150, 360, 350, 450)
    time.sleep(1.5)
else:
    print("10 屏未找到", flush=True)
client.close()
