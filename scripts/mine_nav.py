"""从书架点「我的」tab → dump 页面找福利/奖励入口。"""
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
    print("[mine] connected", flush=True)
    try:
        rows = dump(client, "m0")
        joined = "".join(r[2] for r in rows)
        if "书架" in joined and "今日已获赠币" not in joined:
            client.click(629, 1263)
            time.sleep(3.0)
        rows = dump(client, "m1")
        for kw in ("福利", "签到", "赠币", "奖励", "领币", "活动", "任务"):
            hit = next((r for r in rows if kw in r[2]), None)
            if hit:
                print(f"\n[mine] 点 {hit[2]!r} @({hit[1]:.0f},{hit[0]:.0f})")
                client.click(int(hit[1]), int(hit[0]))
                time.sleep(3.5)
                dump(client, "m2")
                break
        else:
            print("\n[mine] 我的页未见福利类入口")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
