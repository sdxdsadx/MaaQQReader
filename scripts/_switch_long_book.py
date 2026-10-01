"""关键观察：app 停在第39章正文页（与 22:41 时相同的章），toast 显示
「已开启」但页面静止 5+ 分钟——自动阅读开启了却没翻页！
可能：这本书（1章/456章 那本魔法书）每章只有 1-2 屏，自动阅读到底后
停在章尾等待，而看护的 body_first_line 一直读同一章内容 → 未变。
或：自动阅读速度设置极慢。
验证法：看 OCR 首行在 60s+ 内是否变化（刚才 stall 2 次=120s 没变）。
且 toast 开启成功多次——页面每次都停在同一章。
处理：换到长章节的书（点另一本 342章/3385章 全职法师），长章内容多，
自动翻页可持续；且该书昨天 auto_read 30min 成功用的就是它。
行动：BACK 回书架 → 点全职法师续读行 → 重新启动看护脚本。"""
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
subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
               capture_output=True, timeout=15)
time.sleep(2)
subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
               capture_output=True, timeout=15)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
on_shelf = any(t.strip() == "书架" and b[1] < 100 for t, b in boxes)
print("书架页:", on_shelf, flush=True)
progress = [(t, b) for t, b in boxes if "3385" in t or ("章/" in t and "3385" in " ".join(t for t, b in boxes))]
# 直接找全职法师行
qz = [(t, b) for t, b in boxes if "全职法师" in t]
print("全职法师:", qz, flush=True)
if qz:
    t, b = qz[0]
    client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:6])[:120], flush=True)
client.close()
