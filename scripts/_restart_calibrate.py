"""BACK 两次把我们带回书友榜页了（页面栈深）。乱。
最干净路径：重启 app → 跳过开屏 → 书架 → 点书进正文 → 呼菜单校准坐标。
之前这套流程 16:16 时跑通过（16:16 那次失败是因为听书会话，重启后就没了）。
一步到位脚本：重启→跳过→书架→进正文→OCR 菜单坐标。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"
subprocess.run([adb, "-s", dev, "shell", "am", "force-stop", "com.qq.reader"],
               capture_output=True, timeout=20)
time.sleep(3)
subprocess.run([adb, "-s", dev, "shell",
                "monkey -p com.qq.reader -c android.intent.category.LAUNCHER 1"],
               capture_output=True, timeout=30)
time.sleep(14)

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()

# 跳过开屏
s = client.screencap()
skip = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳过" in t]
if skip:
    t, b = skip[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
    print("已跳开屏", flush=True)

# 点书进简介
s = client.screencap()
book = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
        if 400 < b[1] < 560 and b[2] > 100]
if book:
    t, b = book[0]
    client.swipe(b[0] + 40, b[1] + 10, b[0] + 40, b[1] + 10, 60)
    time.sleep(3)
    print("已点书:", t, flush=True)

# 简介页找「继续阅读/开始阅读」或点章节
s = client.screencap()
btn = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
       if any(k in t for k in ("继续阅读", "开始阅读", "免费阅读"))]
print("阅读按钮:", btn, flush=True)
if btn:
    t, b = btn[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3.5)

# 进正文后呼菜单，OCR 校准「设置」位置
client.swipe(360, 640, 360, 640, 60)
time.sleep(1.8)
s = client.screencap()
menu = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
        if any(k in t for k in ("设置", "目录", "进度", "书评区", "自动阅读"))]
print("菜单校准:", menu, flush=True)
client.close()
