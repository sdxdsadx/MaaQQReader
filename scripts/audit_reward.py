"""审计: 奖励到账核查——奖励页计数器 + 获奖记录明细。"""
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
    print(f"[{tag}] saved {out.name}")


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

    shot, texts = boxes(client)
    save(client, "t0_reward", shot)
    joined = " ".join(t for t, *_ in texts)

    # 1) 顶部计数器
    m = re.search(r"今日已获赠币\s*(\d+)", joined)
    print(f"[audit] 今日已获赠币 = {m.group(1) if m else '未读到'}")

    # 2) 找获奖记录入口并点开
    rec = find(texts, "获奖记录")
    if rec:
        print(f"[audit] 点获奖记录 @ ({rec[0]},{rec[1]})")
        client.click(rec[0], rec[1])
        time.sleep(4)
        shot2, texts2 = boxes(client)
        save(client, "t1_award_records", shot2)
        print("[audit] 获奖记录页文本:")
        for t, x, y, w, h in texts2[:25]:
            print(f"   ({x},{y}) {t[:40]}")
        # 返回奖励页
        client.click_key(4)
        time.sleep(2)
    else:
        print("[audit] 当前页无「获奖记录」入口；全文本:")
        for t, x, y, w, h in texts[:25]:
            print(f"   ({x},{y}) {t[:40]}")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
