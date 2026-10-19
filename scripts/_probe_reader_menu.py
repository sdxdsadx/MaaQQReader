"""当前正文页（第34章）。按用户方案重构阅读挂机：
①点屏幕中央呼出菜单 ②点底部「设置」 ③在设置面板点「自动阅读」
④轮询检测「自动阅读中」特征 → 确认进入自动阅读态
⑤挂机 30 分钟（页面会弹「你已阅读30分钟，请休息一下」→ 点返回）
⑥回奖励中心领两个相邻代币奖励（阅读20 + 时长30，共40赠币）

先探测菜单结构：点中央 (360,640) → OCR 看菜单布局。"""
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
client.swipe(360, 640, 360, 640, 60)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
