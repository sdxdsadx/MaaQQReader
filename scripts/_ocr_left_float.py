"""用户提示：自动听书开着时无法自动阅读；进入阅读界面后左下角有
「自动阅读浮窗」（听书的悬浮窗），要先点它的 X 关掉，再开自动阅读。
重构 enable_auto_read：
0) 检测正文页左下角浮窗（OCR 找「自动阅读/听书」浮窗文本，区域 y>1000
   或左下 x<250）→ 点其 X 关闭
1) 呼菜单→设置→自动阅读 → BACK 收面板
2) 验证翻页
先活体看当前正文页左下角浮窗长什么样。"""
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
    print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}")
client.close()
