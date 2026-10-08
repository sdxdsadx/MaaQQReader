"""页面又变（我有一座冒险屋=听书自动连播跳书了！），页面在乱跳是因为
听书播放的自动连播。点击操作总被播放状态追赶。
一锤定音方案：force-stop app 重启（清掉听书会话），按昨天验证过的
成功链路走：跳过开屏 → 书架 → 全职法师点书名进正文 → 开自动阅读 →
300 分钟看护。之前这条链 100% 成功过（昨天 auto_read 30min 就是这么跑的）。"""
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
s = client.screencap()
skip = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳过" in t]
if skip:
    t, b = skip[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
    print("跳过开屏", flush=True)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
qz = [(t, b) for t, b in boxes if "全职法师" in t]
print("全职法师:", qz, flush=True)
if qz:
    t, b = qz[0]
    client.swipe(b[0] + 50, b[1] + 15, b[0] + 50, b[1] + 15, 60)
    time.sleep(4)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:6])[:120], flush=True)
client.close()
