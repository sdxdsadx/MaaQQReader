"""_autoread_300.py 是脚本不是模块（import 即执行导航+300min）。
独立写看护启动脚本（导航已完成，直接从正文页开始）。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()

LOG = Path(r"G:\project_X\runtime\logs\autoread_300.log")


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


def press_back():
    import subprocess
    adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
    subprocess.run([adb, "-s", "127.0.0.1:16384", "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=15)
    time.sleep(2)


def enable_auto_read():
    for _ in range(2):
        client.swipe(360, 640, 360, 640, 60)
        time.sleep(1.5)
        texts = " ".join(t for t, b in ocr())
        if "设置" in texts:
            break
    client.swipe(452, 1247, 452, 1247, 60)
    time.sleep(1.5)
    client.swipe(355, 1122, 355, 1122, 60)
    time.sleep(1.2)
    toast = " ".join(t for t, b in ocr())
    press_back()
    time.sleep(1.5)
    if "已开启自动阅读" in toast:
        log("toast: 已开启 ✅")
        return True
    if "已关闭自动阅读" in toast:
        log("toast: 已关闭(原本开着) → 再开")
        for _ in range(2):
            client.swipe(360, 640, 360, 640, 60)
            time.sleep(1.5)
            if "设置" in " ".join(t for t, b in ocr()):
                break
        client.swipe(452, 1247, 452, 1247, 60)
        time.sleep(1.5)
        client.swipe(355, 1122, 355, 1122, 60)
        time.sleep(1.2)
        toast2 = " ".join(t for t, b in ocr())
        press_back()
        time.sleep(1.5)
        ok = "已开启自动阅读" in toast2
        log(f"二次开启: {ok}")
        return ok
    log(f"toast 未见成功: {toast[:60]}")
    return False


def is_auto_reading():
    for _ in range(2):
        client.swipe(360, 640, 360, 640, 60)
        time.sleep(1.5)
        texts = " ".join(t for t, b in ocr())
        if "设置" in texts:
            break
    on = "自动阅读中" in texts
    press_back()
    time.sleep(1.5)
    return on


TOTAL = 300 * 60
log("=== 300 分钟看护启动（正文页就绪） ===")
if is_auto_reading():
    log("已在自动阅读中")
else:
    if not enable_auto_read():
        if not enable_auto_read():
            log("❌ 自动阅读开启失败，退出")
            sys.exit(2)

t0 = time.time()
last = body_first_line()
stall = 0
while time.time() - t0 < TOTAL:
    time.sleep(60)
    remain = int((TOTAL - (time.time() - t0)) / 60)
    boxes = ocr()
    j = " ".join(t for t, b in boxes)
    if ("已阅读" in j and "休息" in j) or "休息一下" in j:
        log("休息弹窗 → BACK")
        press_back()
        time.sleep(2)
        continue
    cur = body_first_line()
    if cur == last:
        stall += 1
        log(f"⚠ 未变({remain}min剩) stall={stall}")
        if stall >= 2:
            log("重开自动阅读")
            if enable_auto_read():
                stall = 0
                last = body_first_line()
            else:
                stall = 1
    else:
        stall = 0
        log(f"翻页正常({remain}min剩)")
        last = cur

log("=== 300 分钟自动阅读完成 ===")
press_back()
time.sleep(2)
log("BACK 收尾完成")
