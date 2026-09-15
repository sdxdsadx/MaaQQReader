"""最终版 300 分钟自动阅读：完整 auto_read 模式（自动翻页 100% 计时长）。
基于 auto_read_30min.py 成熟逻辑，时长参数化 300 分钟，中途每 30 分钟
主动记录进度。前台运行完毕自动退出正文。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client
from auto_read_30min import _verify_book_allowed

LOG = Path(r"G:\project_X\runtime\logs\autoread_final300.log")
client = None


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


def main() -> int:
    global client
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()

    allowed, message = _verify_book_allowed(client)
    if not allowed:
        log(message)
        sys.exit(3)

    total = 300 * 60
    log("=== 最终版 300 分钟自动阅读启动 ===")
    if is_auto_reading():
        log("已在自动阅读中")
    elif not enable_auto_read() and not enable_auto_read():
        log("❌ 开启失败")
        return 2

    t0 = time.time()
    last = body_first_line()
    stall = 0
    next_progress_log = t0 + 1800
    while time.time() - t0 < total:
        time.sleep(60)
        remain = int((total - (time.time() - t0)) / 60)
        boxes = ocr()
        joined = " ".join(t for t, b in boxes)
        if ("已阅读" in joined and "休息" in joined) or "休息一下" in joined:
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
            last = cur
        if time.time() >= next_progress_log:
            log(f"进度: {remain}min 剩，翻页正常")
            next_progress_log = time.time() + 1800

    log("=== 300 分钟自动阅读完成 ===")
    press_back()
    time.sleep(2)
    log("BACK 收尾完成，可去奖励页领取")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
