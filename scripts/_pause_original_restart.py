"""点续读行又进了 AI 朗读播放页（第350章 02:53 播放中 II 暂停键可见）——
这本书的「续读」被听书接管（上次听到 350 章）。
现在在朗读播放页，元素齐全：II 暂停 (333,489)、「查看原文」按钮在下方。
昨天点「查看原文」(494,1112) 成功进正文！执行：暂停 → 查看原文 → 正文
→ 开自动阅读 → 看护。这次看护脚本必须从暂停后的正文页开始（听书已暂停，
会话还在但**自动阅读仍可能被拒**——昨天实测拒绝，重启才清）。
所以顺序：暂停听书 → 查看原文 → force-stop 重启（清会话）→ 落正文
→ 开自动阅读 → 300min。执行。"""
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
client.swipe(333, 489, 333, 489, 60)
time.sleep(2)
s = client.screencap()
orig = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "查看原文" in t]
if orig:
    t, b = orig[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3.5)

# force-stop 清听书会话
subprocess.run([adb, "-s", dev, "shell", "am", "force-stop", "com.qq.reader"],
               capture_output=True, timeout=20)
time.sleep(3)
subprocess.run([adb, "-s", dev, "shell",
                "monkey -p com.qq.reader -c android.intent.category.LAUNCHER 1"],
               capture_output=True, timeout=30)
time.sleep(15)
s = client.screencap()
skip = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳过" in t]
if skip:
    t, b = skip[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
body = [(t, b) for t, b in boxes if 100 < b[1] < 1000 and b[2] > 200 and len(t) > 12]
print("落地正文判断:", len(body) >= 2, "|", " ".join(t for t, b in boxes)[:80], flush=True)
client.close()
