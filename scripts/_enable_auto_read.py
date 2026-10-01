"""设置面板确认：「自动阅读」@ (315,1112) 中心≈(355,1122)。
完整重构方案固化：
①点中央呼菜单 ②点设置(452,1247) ③点自动阅读(355,1122)
④验证「自动阅读中」：自动阅读开启后正文页会逐步滚动，且底部可能出现
提示条。检测方式：连续两次截屏正文内容变化（首行 OCR 不同）=自动翻页中。
⑤30 分钟后弹「你已阅读30分钟」→ 点返回
⑥奖励中心领 2 个相邻代币奖励（+20 每日阅读 / +20 阅读时长档）共 40。
先固化 ①②③ + ④检测。"""
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

def first_line():
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    body = [(t, b) for t, b in boxes if b[1] > 100 and b[1] < 1000]
    body.sort(key=lambda x: x[1][1])
    return body[0][0] if body else "", 117

l1, _ = first_line()
client.swipe(360, 640, 360, 640, 60); time.sleep(1.5)   # 呼菜单
client.swipe(452, 1247, 452, 1247, 60); time.sleep(1.5) # 设置
client.swipe(355, 1122, 355, 1122, 60); time.sleep(2)   # 自动阅读
l2, _ = first_line()
time.sleep(8)
l3, _ = first_line()
print(f"L1={l1[:20]}")
print(f"L2={l2[:20]}")
print(f"L3={l3[:20]}")
print("自动翻页中:" , (l2 != l1) or (l3 != l2))
client.close()
