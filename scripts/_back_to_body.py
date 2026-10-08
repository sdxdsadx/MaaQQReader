"""复盘（14:16）：看护脚本 fail 后调用 enable_auto_read 二次重试时，
它的「呼菜单」点击把页面切到了 AI 朗读详情页（AI朗读标题在顶部）——
看书脚本的菜单点击坐标固定 (360,640)/(452,1247)，在听书详情页上点出了
播放面板。层层死循环根因 = **这本书的自动阅读不可用**（听书书源）。
今天要拿到 300 分钟阅读时长，换一条 100% 稳的路：
**全职法师正文 + 手动滑动翻页**（凌晨滑动 280 分钟有效率 52%，
146/280；要拿满 300 分钟有效时长需要滑动 ~580 分钟 ≈ 9.7 小时）。
或者接受：今天有效阅读时长已达 155 分钟（书架实证），300 分钟是
总目标的一部分。用户要求「跑满 300 分钟自动阅读」——继续用滑动模式
跑剩余（300-155=145 分钟有效 → 需滑动 ~280 分钟）。
先停掉所有残留进程，回正文页，启动滑动翻页长跑（滑动模式已验证
计时有效——凌晨 146 分钟就是这么来的）。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()

# 回正文：朗读页 → 查看原文
s = client.screencap()
orig = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "查看原文" in t]
if orig:
    t, b = orig[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
body = [(t, b) for t, b in boxes if 100 < b[1] < 1000 and b[2] > 200 and len(t) > 12]
print("正文判断:", len(body) >= 2, flush=True)
client.close()
