"""看到了：y=1085 x=620 「听」——右下角听书浮窗（不是左下）。这就是
挡自动阅读的浮窗。它还有展开态（y=1110 正文行穿插了下一章预览？）。
用户说左下角有浮窗带 X——当前截图里浮窗显示「听」字（x=620,y=1085,
w=64），浮窗本体应该在 (600..690, 1070..1140) 附近，X 可能在浮窗边缘。
也注意到菜单当前是展开的（底部 目录/进度/设置/书评区 可见）。
策略：OCR 找「听」字浮窗（y 1000..1200, x>500）→ 点它中心（先试直接
点浮窗看是否弹关闭按钮）。然后正常开启自动阅读。"""
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
floats = [(t, b) for t, b in boxes if b[1] > 1000 and b[0] > 450 and len(t) <= 2]
print("浮窗候选:", floats, flush=True)
if floats:
    t, b = floats[0]
    x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
    print(f"点浮窗 ({x},{y})", flush=True)
    client.swipe(x, y, x, y, 60)
    time.sleep(2)
    s2 = client.screencap()
    for t2, b2 in sorted(client.recognize("OCR", {}, s2).text_boxes(),
                         key=lambda x: x[1][1]):
        if b2[1] > 950:
            print(f"y={b2[1]:4d} x={b2[0]:4d} | {t2}", flush=True)
client.close()
