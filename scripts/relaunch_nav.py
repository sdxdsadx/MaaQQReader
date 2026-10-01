"""重启 QQReader → 书架找奖励横幅 → 进 H5 奖励页 → dump 游戏卡区域。"""
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


def dump(client, tag, save=True):
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
    for cy, cx, txt in rows[:40]:
        print(f"  y={cy:6.0f} x={cx:5.0f} | {txt[:56]}")
    if len(rows) > 40:
        print(f"  ...({len(rows)-40} more)")
    return rows


def main() -> int:
    config = load_config(_ROOT / "configs" / "qqreader.local.json")
    client = build_maa_client(config)
    client.connect()
    print("[relaunch] connected", flush=True)
    try:
        client.stop_app("com.qq.reader")
        time.sleep(2.0)
        client.start_app("com.qq.reader")
        time.sleep(10.0)
        rows = dump(client, "L0")
        joined = "".join(r[2] for r in rows)
        # 处理可能的公告/弹窗
        if "确定退出QQ阅读" in joined:
            client.click(538, 1242)
            time.sleep(2.0)
            rows = dump(client, "L0b")
            joined = "".join(r[2] for r in rows)
        # 找奖励横幅
        banner = None
        for kw in ("本周阅读时长", "再读", "阅读时长", "领赠币"):
            banner = next((r for r in rows if kw in r[2]), None)
            if banner:
                break
        if banner:
            print(f"\n[relaunch] 点横幅 {banner[2]!r} @({banner[1]:.0f},{banner[0]:.0f})")
            client.click(int(banner[1]), int(banner[0]))
            time.sleep(4.0)
        else:
            print("\n[relaunch] 重启后书架仍无横幅, 点击历史横幅位 (173,196) 试探")
            client.click(173, 150)
            time.sleep(3.0)
        rows = dump(client, "L1")
        joined = "".join(r[2] for r in rows)
        if "今日已获赠币" in joined:
            print("\n[relaunch] === 已到 H5 奖励页 ===")
            # 滚到游戏卡区
            client.swipe(360, 1000, 360, 420, 400)
            time.sleep(1.2)
            rows = dump(client, "L2_gamecard")
            joined = "".join(r[2] for r in rows)
            btn = next((r for r in rows if "去玩游戏" in r[2]), None)
            if btn:
                print(f"\n[relaunch] 游戏卡按钮 {btn[2]!r} @({btn[1]:.0f},{btn[0]:.0f})")
            else:
                client.swipe(360, 1000, 360, 420, 400)
                time.sleep(1.2)
                rows = dump(client, "L3_gamecard2")
                btn = next((r for r in rows if "去玩游戏" in r[2]), None)
                print(f"\n[relaunch] 游戏卡按钮: {btn}")
        else:
            print("\n[relaunch] 未到奖励页, joined=", joined[:150])
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
