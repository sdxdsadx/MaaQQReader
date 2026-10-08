"""诊断/干预: 刷新奖励页并判定游戏卡「去玩游戏/立即领取/已领取」状态。

用法: python scripts/manual_refresh_probe.py --config configs/qqreader.local.json [--no-refresh]
动作: 回顶部 → (可选)下拉刷新 → 滚到游戏卡 → 截图 + OCR 关键词命中
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config  # noqa: E402
from qqreader.maa.factory import build_maa_client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--no-refresh", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    client = build_maa_client(config)
    client.connect()
    print("[probe] connected", flush=True)

    def swipe(x1, y1, x2, y2, ms=400):
        client.swipe(x1, y1, x2, y2, ms)
        time.sleep(0.8)

    # 1) 回到顶部
    for _ in range(3):
        swipe(360, 400, 360, 1000, 300)

    # 2) 下拉刷新（顶部下拖）
    if not args.no_refresh:
        swipe(360, 300, 360, 1100, 500)
        time.sleep(3.0)

    # 3) 滚到游戏卡区域
    for _ in range(3):
        swipe(360, 1000, 360, 400, 400)

    time.sleep(2.0)
    shot = client.screencap()
    if not shot:
        print("[probe] screencap FAILED")
        client.close()
        return 1
    out = _ROOT / "runtime/screenshots/manual_refresh_probe.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(shot.data if hasattr(shot, "data") else shot)
    print(f"[probe] saved ({out.stat().st_size} bytes)", flush=True)

    # 4) OCR 关键词判定
    ocr = client.recognize("OCR", {}, shot)
    texts = list(ocr.all_texts()) if (ocr.hit or ocr.detail) else []
    keys = ("去玩游戏", "立即领取", "已领取", "明日再来", "今日已获赠币", "回到顶部", "获奖记录", "在线玩")
    hits = [t for t in texts if any(k in t for k in keys)]
    print("[probe] 关键命中:")
    for h in hits:
        print("  -", h)
    if not hits:
        print("  (无命中, 全量文本前 15 条:)")
        for t in texts[:15]:
            print("  ·", t)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
