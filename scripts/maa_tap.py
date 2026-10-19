"""诊断/干预脚本: 用项目自身的 MaaFW 控制器精准点击 H5 游戏协议页。
用法: python scripts/maa_tap.py --config configs/qqreader.local.json --mode agree
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--mode", default="agree")
    args = parser.parse_args()

    config = load_config(args.config)
    client = build_maa_client(config)
    client.connect()
    print("[maa] connected", flush=True)

    # 坐标基于 720x1280 截图 OCR 标定
    # 勾选框(空方形) (165,1035); 蓝色"同意"文字 (355,651); "进入游戏"按钮 (356,927)
    taps = {
        "agree": [(165, 1035), (355, 651), (356, 927)],
        "checkbox": [(165, 1035)],
        "enter": [(356, 927)],
    }.get(args.mode, [(165, 1035)])
    for x, y in taps:
        ok = client.click(x, y)
        print(f"[maa] click({x},{y}) -> {ok}", flush=True)
        time.sleep(2.0)

    time.sleep(4)
    shot = client.screenshot()
    if shot:
        out = Path("G:/project_X/runtime/screenshots/maa_tap_last.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(shot)
        print(f"[maa] screenshot saved: {out} ({len(shot)} bytes)", flush=True)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
