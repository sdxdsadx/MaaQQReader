"""还在第39章正文页。自动阅读模式开着但书停章尾——改用手动滑动翻页
（昨天验证 tap 翻页有效的方案：每 18s 点 (600,640)）。
但先试滑动（点右下角 1/3 处翻页在部分书无效，用 swipe 从右往左）：
每 20s swipe(600,640 → 120,640)。长跑 280 分钟由后台脚本执行，
内嵌 stall 检测（OCR 首行）+ 每章尾自动「下一章」点击（OCR 找 下一章）。"""
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

LOG = Path(r"G:\project_X\runtime\logs\autoread300_watch.log")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def ocr():
    s = client.screencap()
    return client.recognize("OCR", {}, s).text_boxes()


def body_first_line():
    boxes = [(t, b) for t, b in ocr() if 100 < b[1] < 1000 and b[0] < 600 and b[2] > 40]
    boxes.sort(key=lambda x: x[1][1])
    return boxes[0][0] if boxes else ""


def swipe_page():
    subprocess.run([adb, "-s", dev, "shell",
                    "input swipe 620 640 100 640 300"], capture_output=True, timeout=15)


TOTAL = 280 * 60
log("=== 切换滑动翻页模式（280 分钟） ===")
t0 = time.time()
last = body_first_line()
stall = 0
taps = 0
while time.time() - t0 < TOTAL:
    swipe_page()
    taps += 1
    time.sleep(18)
    remain = int((TOTAL - (time.time() - t0)) / 60)
    cur = body_first_line()
    boxes = ocr()
    j = " ".join(t for t, b in boxes)
    if "已阅读" in j and "休息" in j:
        log("休息弹窗 → BACK")
        subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
                       capture_output=True, timeout=15)
        time.sleep(2)
        continue
    if cur == last:
        stall += 1
        if stall >= 3:
            log(f"⚠ 连续{stall}次未变({remain}min剩) 可能章尾 → 找下一章")
            nxt = [(t, b) for t, b in boxes if "下一章" in t]
            if nxt:
                t, b = nxt[0]
                client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
                log("点下一章")
            stall = 0
        else:
            log(f"未变({remain}min剩) stall={stall}")
    else:
        stall = 0
        if taps % 10 == 0:
            log(f"翻页中({remain}min剩) taps={taps}")
    last = cur

log(f"=== 滑动翻页完成 taps={taps} ===")
subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
               capture_output=True, timeout=15)
log("BACK 收尾")
