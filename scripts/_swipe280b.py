"""崩溃原因：旧看护进程还占着日志文件句柄（kill 只杀了 watch 主进程，
句柄未释放或还有存活实例）。修正：换独立日志文件名 + 确认无 python 残留。"""
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
from auto_read_30min import (
    _verify_book_allowed,
    click_target_book,
    return_to_capturable,
    return_to_shelf,
)

LOG = Path(r"G:\project_X\runtime\logs\swipe280.log")
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


def swipe_page():
    subprocess.run([adb, "-s", dev, "shell",
                    "input swipe 620 640 100 640 300"], capture_output=True, timeout=15)


def main() -> int:
    global client
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()

    # 书源守门改用「书架上的 Maa 选书结果」判定（不再扫正文页顶部），
    # 所以先回书架再校验，随后由 Maa 选中白名单书目进正文，与 auto_read 一致。
    return_to_capturable()
    return_to_shelf()
    allowed, message = _verify_book_allowed(client)
    if not allowed:
        log(message)
        sys.exit(3)
    log(f"书源校验通过：{message}")
    click_target_book()

    total = 280 * 60
    log("=== 滑动翻页模式启动（280 分钟） ===")
    t0 = time.time()
    last = body_first_line()
    stall = 0
    taps = 0
    while time.time() - t0 < total:
        swipe_page()
        taps += 1
        time.sleep(18)
        remain = int((total - (time.time() - t0)) / 60)
        boxes = ocr()
        joined = " ".join(t for t, b in boxes)
        if "已阅读" in joined and "休息" in joined:
            log("休息弹窗 → BACK")
            subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
                           capture_output=True, timeout=15)
            time.sleep(2)
            continue
        cur = body_first_line()
        if cur == last:
            stall += 1
            if stall >= 3:
                log(f"⚠ 连续{stall}次未变({remain}min剩)")
                nxt = [(t, b) for t, b in boxes if "下一章" in t]
                if nxt:
                    _, box = nxt[0]
                    client.swipe(box[0] + box[2] // 2, box[1] + box[3] // 2,
                                 box[0] + box[2] // 2, box[1] + box[3] // 2, 60)
                    log("点下一章")
                stall = 0
        else:
            stall = 0
            if taps % 15 == 0:
                log(f"翻页中({remain}min剩) taps={taps}")
        last = cur

    log(f"=== 滑动翻页完成 taps={taps} ===")
    subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=15)
    log("BACK 收尾完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
