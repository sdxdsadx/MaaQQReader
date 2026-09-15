"""自动阅读 30 分钟完整方案（重构 legacy 纯挂机为「开自动阅读+盯进度」）。
流程：
  A. 开启自动阅读（呼菜单→设置→自动阅读），验证自动翻页
  B. 30 分钟看护：每 60s 检查首行变化（自动翻页证据），停了就重开
  C. 到点后 OCR「你已阅读30分钟」弹窗 → 点返回关闭
  D. 回主页 → 进奖励中心 → 领两个相邻代币奖励（+20/+20 共 40）
用法: python scripts/auto_read_30min.py
"""
from __future__ import annotations

import sys
import time
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

LOG = ROOT / "runtime" / "logs" / "auto_read.log"
ALLOWED_BOOK_KEYWORDS = ("宇智波",)
client = None


def log(msg: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def ocr_all():
    s = client.screencap()
    return client.recognize("OCR", {}, s).text_boxes()


def _verify_book_allowed(client) -> tuple[bool, str]:
    """确认当前页面顶部标题属于允许自动阅读的书源。"""
    screenshot = client.screencap()
    boxes = client.recognize("OCR", {}, screenshot).text_boxes()
    title_lines = []
    for text, box in boxes:
        text = str(text).strip()
        if text and box[1] < 100:
            title_lines.append(text)

    recognized = next(
        (text for text in title_lines if any(keyword in text for keyword in ALLOWED_BOOK_KEYWORDS)),
        None,
    )
    if recognized is not None:
        return True, recognized

    chapter = next((text for text in title_lines if re.search(r"第\s*\d+\s*章", text)), None)
    observed = chapter or (" / ".join(title_lines) if title_lines else "未识别到正文页标题")
    return False, f"当前书不在自动阅读白名单: {observed}"


def body_first_line():
    boxes = [
        (t, b) for t, b in ocr_all()
        if 100 < b[1] < 1000 and b[0] < 600 and b[2] > 40
    ]
    boxes.sort(key=lambda x: x[1][1])
    return boxes[0][0] if boxes else ""


def enable_auto_read() -> bool:
    """幂等呼菜单→设置→点自动阅读，用 toast 文字判定结果（可靠）。"""
    for _ in range(2):
        client.swipe(360, 640, 360, 640, 60)
        time.sleep(1.5)
        texts = " ".join(t for t, b in ocr_all())
        if "设置" in texts:
            break
    client.swipe(452, 1247, 452, 1247, 60)
    time.sleep(1.5)
    client.swipe(355, 1122, 355, 1122, 60)
    time.sleep(1.2)  # toast 窗口
    toast = " ".join(t for t, b in ocr_all())
    client.swipe(360, 640, 360, 640, 0)
    time.sleep(1.5)
    if "已开启自动阅读" in toast:
        log("toast: 已开启自动阅读 ✅")
        return True
    if "已关闭自动阅读" in toast:
        # 原本开着，被我关了 → 再开一次
        log("toast: 已关闭（原本开着）→ 重新开启")
        for _ in range(2):
            client.swipe(360, 640, 360, 640, 60)
            time.sleep(1.5)
            if "设置" in " ".join(t for t, b in ocr_all()):
                break
        client.swipe(452, 1247, 452, 1247, 60)
        time.sleep(1.5)
        client.swipe(355, 1122, 355, 1122, 60)
        time.sleep(1.2)
        toast2 = " ".join(t for t, b in ocr_all())
        client.swipe(360, 640, 360, 640, 0)
        time.sleep(1.5)
        ok = "已开启自动阅读" in toast2
        log(f"二次开启: {ok}")
        return ok
    log(f"toast 未见开启成功: {toast[:60]}")
    return False


def is_auto_reading() -> bool:
    """呼菜单看设置面板标题是否为「自动阅读中」——确定性判定。"""
    for _ in range(2):
        client.swipe(360, 640, 360, 640, 60)
        time.sleep(1.5)
        texts = " ".join(t for t, b in ocr_all())
        if "设置" in texts:
            break
    on = "自动阅读中" in texts
    # 收起菜单
    client.swipe(360, 640, 360, 640, 0)
    time.sleep(1.5)
    return on


def main() -> int:
    global client
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()

    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=30)
    args, _ = ap.parse_known_args()
    duration = args.minutes * 60
    log(f"=== 自动阅读 {args.minutes} 分钟开始 ===")
    allowed, message = _verify_book_allowed(client)
    if not allowed:
        log(message)
        sys.exit(3)
    if is_auto_reading():
        log("已在自动阅读中 → 直接看护")
    elif not enable_auto_read():
        # toggle 可能把原本开着的关了：再 toggle 一次并验证
        if not enable_auto_read():
            log("❌ 自动阅读无法开启（两次尝试均无翻页）")
            return 2
    t0 = time.time()
    last_line = body_first_line()
    stall = 0
    while time.time() - t0 < duration:
        time.sleep(60)
        remain = int((duration - (time.time() - t0)) / 60)
        time.sleep(20)  # 自动阅读一屏约 20s+，60s+20s 采样窗内必有翻页
        cur = body_first_line()
        if cur == last_line:
            stall += 1
            log(f"⚠ 首行未变({remain}min 剩) stall={stall}")
            if stall >= 2:
                log("自动阅读疑似停止 → 重新开启")
                if not enable_auto_read():
                    stall = 1
                    continue
                stall = 0
        else:
            stall = 0
            log(f"翻页正常 ({remain}min 剩)")
            last_line = cur
        # 提前检测 30 分钟弹窗
        for t, b in ocr_all():
            if ("已阅读" in t and "分钟" in t) or "休息一下" in t:
                log("检测到 30 分钟休息弹窗 → 提前结束")
                client.swipe(360, 640, 360, 640, 0)
                t0 = 0  # break outer via time check
                break
    log(f"{args.minutes} 分钟到 → 关闭弹窗/返回")
    for _ in range(3):
        boxes = ocr_all()
        hit = any(("已阅读30分钟" in t) or ("休息一下" in t) for t, b in boxes)
        client.swipe(360, 640, 360, 640, 0)  # BACK (keyevent4 equivalent not needed; use key)
        time.sleep(2)
        if hit:
            log("弹窗已处理")
            break
    log("=== 自动阅读挂机完成 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
