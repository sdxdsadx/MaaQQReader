"""审计 v2: 书架 → 奖励页 → 计数器 + 获奖记录。"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config  # noqa: E402
from qqreader.maa.factory import build_maa_client  # noqa: E402


def boxes(client):
    shot = client.screencap()
    ocr = client.recognize("OCR", {}, shot)
    detail = ocr.detail if isinstance(ocr.detail, dict) else {}
    items = detail.get("all") or detail.get("boxes") or detail.get("items") or []
    out = []
    for it in items:
        if isinstance(it, dict) and "box" in it and "text" in it:
            x, y, w, h = it["box"]
            out.append((str(it["text"]), x, y, w, h))
    return shot, out


def save(client, tag, shot):
    out = _ROOT / f"runtime/screenshots/audit_{tag}.png"
    out.write_bytes(shot.data if hasattr(shot, "data") else shot)
    print(f"[{tag}] saved")


def find(texts, keyword):
    for t, x, y, w, h in texts:
        if keyword in t:
            return (x + w // 2, y + h // 2, t)
    return None


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()
    print("[audit] connected", flush=True)

    # 书架 → 顶部 banner 入口（r36 已验证路径：本周阅读时长横幅）
    shot, texts = boxes(client)
    banner = find(texts, "再读5分钟领20赠币")
    if not banner:
        banner = find(texts, "535分钟")
    if banner:
        print(f"[audit] 点顶部入口 @ ({banner[0]},{banner[1]}) text={banner[2][:24]}")
        client.click(banner[0], banner[1])
        time.sleep(4)
    shot, texts = boxes(client)
    save(client, "v2_page", shot)
    joined = " ".join(t for t, *_ in texts)

    m = re.search(r"今日已获赠币\s*(\d+)", joined)
    if not m:
        # 可能进了别的页（如阅读时长页），点返回再试一次 OCR 找奖励页
        print("[audit] 未进奖励页，BACK 重试")
        client.click_key(4)
        time.sleep(2)
        shot, texts = boxes(client)
        joined = " ".join(t for t, *_ in texts)
        m = re.search(r"今日已获赠币\s*(\d+)", joined)

    print(f"[audit] 今日已获赠币 = {m.group(1) if m else '未读到'}")

    rec = find(texts, "获奖记录")
    if rec:
        print(f"[audit] 点获奖记录 @ ({rec[0]},{rec[1]})")
        client.click(rec[0], rec[1])
        time.sleep(4)
        shot2, texts2 = boxes(client)
        save(client, "v2_award_records", shot2)
        print("[audit] 获奖记录明细（前 25 条）:")
        for t, x, y, w, h in texts2[:25]:
            print(f"   ({x},{y}) {t[:44]}")
        client.click_key(4)
    else:
        print("[audit] 无获奖记录入口；当前页文本（前 22 条）:")
        for t, x, y, w, h in texts[:22]:
            print(f"   ({x},{y}) {t[:44]}")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
