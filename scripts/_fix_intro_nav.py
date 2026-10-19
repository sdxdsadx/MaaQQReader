"""失败点：点书后停在「简介页」（OCR 显示 简介/评分），不在正文页——
「简介页找继续阅读」步骤的按钮 OCR 没找到（btn 为空跳过），然后直接
呼菜单失败。简介页需要下滑到底找「继续阅读」按钮或点目录进正文。
修：点书后如果检测到「简介」字样，下滑找 阅读按钮/点最新章节。
快速热修脚本继续跑（进程已退出）。"""
import subprocess
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

# 当前在简介页：下滑找阅读按钮
client.swipe(360, 1100, 360, 300, 500)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
btn = [(t, b) for t, b in boxes if any(k in t for k in ("继续阅读", "开始阅读", "免费阅读", "阅读全文"))]
print("按钮:", btn, flush=True)
if btn:
    t, b = btn[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:6])[:130], flush=True)
else:
    print("仍无按钮，打印全页：", flush=True)
    for t, b in sorted(boxes, key=lambda x: x[1][1])[-8:]:
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
