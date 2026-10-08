"""自动阅读开启失败：因为脚本开始时**已经在自动阅读中**（我刚才
_enable_auto_read.py 开过），重复点击「自动阅读」把它关了！
且首行停在「打卡」提示条。修复脚本逻辑：
- enable_auto_read 前先检测当前是否已在自动阅读（连续两次首行不同即已在跑）
- 若已在跑 → 直接进入看护循环，不要再点开关
先手动确认当前状态：呼菜单看「自动阅读」开关状态（设置面板里按钮是否有
高亮/开启字样），然后改进脚本。"""
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
client.swipe(360, 640, 360, 640, 60); time.sleep(1.5)
client.swipe(452, 1247, 452, 1247, 60); time.sleep(1.5)
s = client.screencap()
boxes = client.recognize("OCR", {"roi": [0, 1050, 720, 190]}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}")
client.close()
