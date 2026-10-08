"""进展：toast 判定生效（「已在自动阅读中→直接看护」=面板标题判定成功）。
但看护循环误报 stall——原因：自动阅读一屏 20s+，60s 采样窗本应翻 2-3 屏，
却两次「未变」……等等，11:48 开启成功后页面在自动滚动，log 显示 28min/27min
连续未变——可能自动阅读翻页停在**章节末尾**（第35章末尾要点「下一章」）？
自动阅读到章节尾会自动跳下一章，或者**卡在末页**等待。
活体确认：当前首行 + 是否有「下一章」按钮。"""
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
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
