"""app 在奖励页（用户手动领了听书 +20，180 = 160+20）。
从奖励页进正文：BACK 回书架 → 点续读行 → 进正文 → 启动 300min 看护。
一条龙脚本。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()

def ocr():
    s = client.screencap()
    return client.recognize("OCR", {}, s).text_boxes()

# BACK 回书架
subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
               capture_output=True, timeout=15)
time.sleep(2.5)
s = client.screencap()
boxes = ocr()
progress = [(t, b) for t, b in boxes if "章/" in t]
print("续读行:", progress[:2], flush=True)
if progress:
    t, b = progress[0]
    client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
    time.sleep(3.5)
    # 进度跳转确认页处理
    s2 = client.screencap()
    jump = [(t, b) for t, b in ocr() if "跳转" in t]
    if jump:
        t, b = jump[-1]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(3.5)
    s3 = client.screencap()
    texts = client.recognize("OCR", {}, s3).all_texts()
    print("正文:", " | ".join(texts[:5])[:110], flush=True)
client.close()
print("正文就绪，启动 _autoread_final300.py")
