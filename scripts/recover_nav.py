"""手工恢复导航: BACK → 我的 tab → OCR dump → 找福利/奖励入口。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config  # noqa: E402
from qqreader.maa.factory import build_maa_client  # noqa: E402

SHOT_DIR = _ROOT / "runtime" / "screenshots"


def dump(client, tag):
    shot = client.screencap()
    out = SHOT_DIR / f"probe11_{tag}.png"
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_bytes(shot.data if hasattr(shot, "data") else shot)
    ocr = client.recognize("OCR", {}, shot)
    items = (ocr.detail or {}).get("all", []) if isinstance(ocr.detail, dict) else []
    rows = sorted(
        [(it["box"][1] + it["box"][3] / 2, it["box"][0] + it["box"][2] / 2,
          str(it.get("text", ""))) for it in items]
    )
    print(f"\n===== [{tag}] {len(rows)} boxes =====")
    for cy, cx, txt in rows:
        print(f"  y={cy:6.0f} x={cx:5.0f} | {txt[:56]}")
    return rows


def main() -> int:
    config = load_config(_ROOT / "configs" / "qqreader.local.json")
    client = build_maa_client(config)
    client.connect()
    print("[recover] connected", flush=True)
    try:
        dump(client, "r0")
        # 连续 BACK 两次脱离阅读页
        client.click_key(4)
        time.sleep(2.0)
        client.click_key(4)
        time.sleep(2.0)
        dump(client, "r1")
        # 点「我的」tab
        client.click(629, 1263)
        time.sleep(3.0)
        rows = dump(client, "r2")
        joined = "".join(r[2] for r in rows)
        for kw in ("福利", "签到", "赠币", "奖励", "任务", "领币", "活动"):
            hit = next((r for r in rows if kw in r[2]), None)
            if hit:
                print(f"\n[recover] 点 {hit[2]!r} @({hit[1]:.0f},{hit[0]:.0f})")
                client.click(int(hit[1]), int(hit[0]))
                time.sleep(3.5)
                dump(client, "r3")
                break
        else:
            print("\n[recover] 我的页未见福利入口, joined=", joined[:200])
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
