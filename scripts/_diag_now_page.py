"""ReadingGotoShelf 点了 (67,1243) 但三个找书节点还是全失败——
点击的 y=1243 是「书城」还是「书架」？之前 OCR: 书架 box=(70,1250,38,26)
中心 x=89。我用的 roi=[0,1200,180,80] expected=书架，Click 点了 (67,1243)。
但书城页 OCR 里 y=1250 是「书架」「书城」「发现」「我的」——底部导航在 1250。
点 (67,1243) 应该命中「书架」。可三个节点 OCR/模板还是全败……

直接抓当前屏幕看点完后在哪个页。如果底部导航点击没生效（app 当时在奖励页！
——刚才 _diag_reading_page 显示 app 在奖励页，奖励页底部导航可能不同），
「书架」点不到或页面跳转不对。看看现在屏幕。"""
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
print("=== 当前页 OCR ===")
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
