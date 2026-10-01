"""模拟器已恢复（16384 + QQ阅读 pid 2475）。
300 分钟自动阅读执行方案（基于 auto_read_30min.py 验证过的逻辑）：
1. 导航：跳过开屏 → 书架 → 点书进正文
2. 自动阅读开启（toast 判定，失败重启一次兜底）
3. 300 分钟看护：每 80s 首行变化检测，stall 2 次重开自动阅读，
   每 30 分钟处理一次「休息一下」弹窗（BACK）
4. 中途赠币/时长每 30 分钟记录一次
写专用脚本 _autoread_300.py（长跑版，落盘日志可断点续跑）。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import subprocess

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

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
    subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=15)
    time.sleep(2)


def enable_auto_read():
    """幂等呼菜单→设置→自动阅读，toast 判定。"""
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


# 导航到正文：重启 app → 跳过开屏 → 书架 → 点书
log("重启 app 清状态")
subprocess.run([adb, "-s", dev, "shell", "am", "force-stop", "com.qq.reader"],
               capture_output=True, timeout=20)
time.sleep(3)
subprocess.run([adb, "-s", dev, "shell",
                "monkey -p com.qq.reader -c android.intent.category.LAUNCHER 1"],
               capture_output=True, timeout=30)
time.sleep(14)
s = client.screencap()
skip = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳过" in t]
if skip:
    t, b = skip[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
    log("已跳开屏")

# 点第一本书进正文
s = client.screencap()
book = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
        if 400 < b[1] < 560 and b[2] > 100]
if book:
    t, b = book[0]
    client.swipe(b[0] + 40, b[1] + 10, b[0] + 40, b[1] + 10, 60)
    time.sleep(3.5)
    log(f"已点书: {t}")

# 简介页找继续阅读
s = client.screencap()
btn = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
       if any(k in t for k in ("继续阅读", "开始阅读", "免费阅读"))]
if btn:
    t, b = btn[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3.5)
    log("简介页进入正文")

if is_auto_reading():
    log("已在自动阅读中")
else:
    if not enable_auto_read():
        if not enable_auto_read():
            log("❌ 自动阅读开启失败")
            sys.exit(2)

# 300 分钟看护
TOTAL = 300 * 60
t0 = time.time()
last = body_first_line()
stall = 0
last_popup = t0
while time.time() - t0 < TOTAL:
    time.sleep(60)
    remain = int((TOTAL - (time.time() - t0)) / 60)
    cur = body_first_line()
    boxes = ocr()
    j = " ".join(t for t, b in boxes)
    if ("已阅读" in j and "分钟" in j and "休息" in j) or "休息一下" in j:
        log("检测到休息弹窗 → BACK")
        press_back()
        time.sleep(2)
        continue
    if cur == last:
        stall += 1
        log(f"⚠ 首行未变({remain}min剩) stall={stall}")
        if stall >= 2:
            log("疑似停止 → 重开自动阅读")
            if not enable_auto_read():
                stall = 1
            else:
                stall = 0
                last = body_first_line()
    else:
        stall = 0
        log(f"翻页正常({remain}min剩)")
        last = cur

log("=== 300 分钟自动阅读完成 ===")

# 收尾：关自动阅读可选（保留），退出正文回书架
press_back()
time.sleep(2)
log("已 BACK 退出，完成")
