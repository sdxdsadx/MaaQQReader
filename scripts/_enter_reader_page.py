"""自动阅读开启失败：当前不在正文页！OCR 显示「简介/评分/第1章」——
DirectReadingFlow 第二轮 SUCCESS 后停留页=书籍详情页（不是正文页也不是
书架）。auto_read 脚本假设正文页（呼菜单/设置按钮坐标）——在详情页全错位。
先活体导到正文页：点「继续阅读/开始阅读」按钮。OCR 找按钮。"""
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
btn = [(t, b) for t, b in boxes if any(k in t for k in ("继续阅读", "开始阅读", "免费阅读", "阅读"))]
print("候选按钮:", btn[:3], flush=True)
if btn:
    t, b = btn[0]
    x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
    print(f"点 {t} @ ({x},{y})", flush=True)
    client.swipe(x, y, x, y, 60)
    time.sleep(3)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:6])[:140], flush=True)
client.close()
