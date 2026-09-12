"""滑块验证码自动求解（活体闭环，2026-09-12 活体迭代实证）。

对当前模拟器屏幕循环执行「截图 → detect_slide → sendevent 拟人滑动 →
等待 → OCR 复查」，直到验证码消失。可重复使用：

    D:/python/python.exe scripts/live_captcha_auto.py [--max-rounds 6]

循环节奏（全部来自活体实证，与 qqreader/captcha/slide.py solve 一致）：

* 每轮都在**新鲜截图**上重检测。滑动被行为校验拒绝后拼图会重新随机化
  （实测 dist 244→340），旧坐标盲补必败；
* 滑动注入复用 scripts/live_sendevent.py 的 sendevent 路径：触屏设备
  getevent -pl 自动探测，B 协议（TRACKING_ID/X/Y/BTN_TOUCH/SYN），
  ease-out 变速 + y 抖动 + 过冲微回调轨迹（匀速直线会被指纹识别回弹）；
* 滑后等 settle(2.5s) 让校验动画走完再复查；
* 检测不到轨道时等 2s 重截图再试（弹窗过渡态），连续两轮检测不到才放弃；
* 成功判据：OCR 无验证码文案（安全验证/拖动滑块/完成拼图），且出现
  奖励页特征（看小视频领好礼/今日已获赠币/玩游戏领赠币等）；
* 求解成功后**只做观测，不点任何业务按钮**。
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# 复用 live_sendevent.py 已验证的 sendevent 注入路径与拟人轨迹。
from live_sendevent import get_touch_dev, human_track, send  # noqa: E402

from qqreader.captcha.slide import detect_slide  # noqa: E402
from qqreader.config import load_config  # noqa: E402
from qqreader.maa.factory import build_maa_client  # noqa: E402

OUT = _ROOT / "runtime" / "screenshots" / "19700105"

CAPTCHA_KEYS = ("安全验证", "拖动下方滑块", "拖动滑块", "滑动验证", "完成拼图")
REWARD_KEYS = ("今日已获赠币", "看小视频领好礼", "玩游戏领赠币", "获奖记录", "明日再来")


def ocr_texts(client, shot) -> list:
    ocr = client.recognize("OCR", {}, shot)
    dd = ocr.detail if isinstance(ocr.detail, dict) else {}
    items = dd.get("all") or dd.get("boxes") or dd.get("items") or []
    return [str(i.get("text", "")) for i in items if isinstance(i, dict)]


def snap(client, tag: str):
    """截图 → 保存 → detect_slide → OCR。返回 (detection, texts)。"""
    s = client.screencap()
    data = s.data if hasattr(s, "data") else s
    (OUT / f"autocap_{tag}.png").write_bytes(data)
    return detect_slide(data), ocr_texts(client, s)


def classify(texts: list) -> tuple:
    joined = " ".join(texts)
    return (
        any(k in joined for k in CAPTCHA_KEYS),
        any(k in joined for k in REWARD_KEYS),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="活体滑块验证码自动求解")
    parser.add_argument("--max-rounds", type=int, default=6)
    parser.add_argument("--settle", type=float, default=2.5)
    args = parser.parse_args()

    config = load_config("configs/qqreader.local.json")
    adb = config.machine.adb_path
    dev = config.machine.adb_address
    client = build_maa_client(config)
    client.connect()
    history = []
    try:
        tdev = get_touch_dev(adb, dev)
        print(f"[init] 触屏设备: {tdev}")
        if not tdev:
            return 1

        redetect_streak = 0
        for round_no in range(1, args.max_rounds + 1):
            d, texts = snap(client, f"r{round_no}_pre")
            cap_on, reward_on = classify(texts)
            print(
                f"[r{round_no}] detect={'FOUND' if d.found else d.error}"
                f" track={d.track} slider={d.slider} center={d.slider_center}"
                f" dist={d.distance} | CAPTCHA_ON={cap_on} REWARD={reward_on}"
            )
            if not cap_on:
                print(f"[r{round_no}] 验证码文案已消失，无需滑动")
                history.append((round_no, 0, "ALREADY_GONE"))
                break
            if not d.found:
                # 过渡态：等 2s 重截图；连续两轮检测不到才放弃。
                redetect_streak += 1
                if redetect_streak >= 2:
                    print(f"[r{round_no}] 连续 {redetect_streak} 轮检测不到轨道 → 放弃")
                    history.append((round_no, 0, "DETECT_FAIL"))
                    break
                time.sleep(2.0)
                history.append((round_no, 0, "WAIT_REDETECT"))
                continue
            redetect_streak = 0

            sx, sy = d.slider_center
            dx = d.distance
            print(f"[r{round_no}] sendevent 拟人滑动: ({sx},{sy}) + {dx}px")
            send(adb, dev, tdev, [(3, 57, 0), (3, 53, sx), (3, 54, sy), (1, 330, 1), (0, 0, 0)])
            time.sleep(0.05)
            for x, y, dt in human_track(sx, sy, dx):
                send(adb, dev, tdev, [(3, 53, x), (3, 54, y), (0, 0, 0)])
                time.sleep(dt / 1000.0)
            time.sleep(random.uniform(0.08, 0.2))
            send(adb, dev, tdev, [(3, 57, -1), (1, 330, 0), (0, 0, 0)])
            time.sleep(args.settle)

            d2, texts2 = snap(client, f"r{round_no}_post")
            cap_on2, reward_on2 = classify(texts2)
            if not cap_on2:
                verdict = "SOLVED" if reward_on2 else "SOLVED_NO_REWARD_TEXT"
                history.append((round_no, dx, verdict))
                print(f"[r{round_no}] post: CAPTCHA_ON=False REWARD={reward_on2} → {verdict}")
                break
            history.append((round_no, dx, "REJECTED_REDETECT"))
            print(f"[r{round_no}] post: 验证码仍在 → 拼图已重新随机化，下一轮重检测")
        else:
            print(f"[done] {args.max_rounds} 轮用尽，验证码仍在")

        print("\n===== 轮次汇总 (round, distance_px, verdict) =====")
        for row in history:
            print("   ", row)
        solved = bool(history) and (
            str(history[-1][2]).startswith("SOLVED") or history[-1][2] == "ALREADY_GONE"
        )
        print(f"[result] {'✅ 验证码已消失' if solved else '❌ 未通过'}")
        return 0 if solved else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
