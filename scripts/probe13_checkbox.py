"""决定性实验: 在协议页实测「OCR框相对勾选 + 进入游戏」是否绕开模态框循环。

步骤: 截图 → 点确定(若有) → 按「我已详细阅读并同意」框左侧偏移勾选 → 点进入游戏 → 截图验证
"""
from __future__ import annotations

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
    result = []
    for it in items:
        if isinstance(it, dict) and "box" in it and "text" in it:
            x, y, w, h = it["box"]
            result.append((str(it["text"]), x, y, w, h))
    return shot, result


def find(texts, keyword):
    for t, x, y, w, h in texts:
        if keyword in t:
            return (x + w // 2, y + h // 2, t, x, y, w, h)
    return None


def shoot(client, tag):
    shot, texts = boxes(client)
    out = _ROOT / f"runtime/screenshots/probe13_{tag}.png"
    out.write_bytes(shot.data if hasattr(shot, "data") else shot)
    print(f"[{tag}] {len(texts)} boxes:")
    for t, x, y, w, h in texts:
        print(f"   ({x},{y},{w},{h}) {t[:28]}")
    return texts


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()
    print("[probe] connected", flush=True)

    texts = shoot(client, "t0_current")

    # 1) 若模态框在，点「确定」关闭
    confirm = find(texts, "确定")
    if confirm:
        cx, cy = confirm[0], confirm[1]
        print(f"[probe] 点确定 @ ({cx},{cy})")
        client.click(cx, cy)
        time.sleep(2.5)
        texts = shoot(client, "t1_after_confirm")

    # 2) 找协议文本框，勾选其左侧圆圈（框左边缘往左 ~45px）
    agree = find(texts, "我已详细阅读并同意")
    if agree:
        _, _, _, ax, ay, aw, ah = agree
        checkbox = (ax - 45, ay + ah // 2)
        print(f"[probe] 协议文本框 left=({ax},{ay},{aw},{h_ah}) → 勾选点击 {checkbox}" if False else f"[probe] 协议文本框 ({ax},{ay},{aw},{ah}) → 勾选点击 {checkbox}")
        client.click(checkbox[0], checkbox[1])
        time.sleep(1.5)
        texts = shoot(client, "t2_after_check")

    # 3) 点进入游戏
    enter = find(texts, "进入游戏")
    if enter:
        print(f"[probe] 点进入游戏 @ ({enter[0]},{enter[1]})")
        client.click(enter[0], enter[1])
        time.sleep(8)
        texts = shoot(client, "t3_after_enter")
        joined = " ".join(t for t, *_ in texts)
        if "确定" in joined or "请先同意" in joined:
            print("[probe] 结论: 模态框复现！勾选未生效或无效")
        else:
            print("[probe] 结论: 未复现模态框（可能已进入游戏）")
    else:
        print("[probe] 未找到「进入游戏」")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
