"""离线 OCR: 对已保存的 TIMEOUT 截图跑 MAA OCR，输出文本框(按 y 排序)。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config  # noqa: E402
from qqreader.maa.client import Screenshot  # noqa: E402
from qqreader.maa.factory import build_maa_client  # noqa: E402

KEY_WORDS = ("去玩游戏", "立即领取", "已领取", "明日再来", "今日已获赠币",
             "回到顶部", "获奖记录", "玩游戏领赠币", "灵画师", "守吾王座")


def main() -> int:
    config = load_config(_ROOT / "configs" / "qqreader.local.json")
    client = build_maa_client(config)
    client.connect()
    try:
        for path in sys.argv[1:]:
            png = Path(path).read_bytes()
            shot = Screenshot(data=png, width=720, height=1280)
            ocr = client.recognize("OCR", {}, shot)
            detail = ocr.detail if isinstance(ocr.detail, dict) else {}
            items = detail.get("all") or []
            rows = []
            for it in items:
                x, y, w, h = it["box"]
                rows.append((y + h / 2, x + w / 2, str(it.get("text", ""))))
            rows.sort()
            print(f"\n===== {Path(path).name} — {len(rows)} boxes =====")
            for cy, cx, txt in rows:
                mark = " <<<" if any(k in txt for k in KEY_WORDS) else ""
                print(f"  y={cy:6.0f} x={cx:5.0f} | {txt[:60]}{mark}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
