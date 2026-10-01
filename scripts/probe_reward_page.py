"""诊断: 用 OCR detail 坐标框导航回奖励页，检查游戏卡状态。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config  # noqa: E402
from qqreader.maa.factory import build_maa_client  # noqa: E402


def ocr_texts(client):
    shot = client.screencap()
    ocr = client.recognize("OCR", {}, shot)
    return shot, ocr


def find_box(ocr, keyword):
    """在 OCR detail 里找包含关键字的文本框，返回 (cx, cy, text)。"""
    detail = ocr.detail if isinstance(ocr.detail, dict) else {}
    items = detail.get("boxes") or detail.get("items") or detail.get("results") or []
    if not items and isinstance(detail, dict):
        # 可能 detail 就是 {text: box} 映射
        for text, box in detail.items():
            if keyword in str(text) and isinstance(box, (list, tuple)) and len(box) >= 4:
                pts = box[0] if isinstance(box[0], (list, tuple)) else box
                try:
                    xs = [p[0] for p in pts] if isinstance(pts[0], (list, tuple)) else [pts[0], pts[2]]
                    ys = [p[1] for p in pts] if isinstance(pts[0], (list, tuple)) else [pts[1], pts[3]]
                    return (sum(xs) / len(xs), sum(ys) / len(ys), str(text))
                except Exception:
                    continue
        return None
    for it in items:
        txt = str(it.get("text", "")) if isinstance(it, dict) else str(it)
        if keyword in txt:
            box = it.get("box") or it.get("points") or it.get("rect")
            if box:
                pts = box[0] if isinstance(box[0], (list, tuple)) else box
                try:
                    xs = [p[0] for p in pts] if isinstance(pts[0], (list, tuple)) else [pts[0], pts[2]]
                    ys = [p[1] for p in pts] if isinstance(pts[0], (list, tuple)) else [pts[1], pts[3]]
                    return (sum(xs) / len(xs), sum(ys) / len(ys), txt)
                except Exception:
                    continue
    return None


def tap_text(client, ocr, keyword):
    box = find_box(ocr, keyword)
    if box:
        cx, cy, txt = box
        print(f"[nav] 点击 {keyword!r} @ ({cx:.0f},{cy:.0f}) text={txt[:30]}")
        client.click(int(cx), int(cy))
        time.sleep(3.0)
        return True
    print(f"[nav] 未找到 {keyword!r}")
    return False


def dump_state(client, tag):
    shot = client.screencap()
    out = _ROOT / f"runtime/screenshots/nav_{tag}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(shot.data if hasattr(shot, "data") else shot)
    ocr = client.recognize("OCR", {}, shot)
    texts = list(ocr.all_texts()) if (ocr.hit or ocr.detail) else []
    keys = ("去玩游戏", "立即领取", "已领取", "明日再来", "今日已获赠币", "回到顶部", "获奖记录", "在线玩", "玩游戏领赠币", "阅读时长")
    hits = [t for t in texts if any(k in t for k in keys)]
    print(f"[probe] {tag}: 命中 {len(hits)} / 共 {len(texts)}")
    for h in hits:
        print("   -", h)
    for t in texts[:8]:
        print("   ·", t)
    return ocr, texts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(args.config)
    client = build_maa_client(config)
    client.connect()
    print("[nav] connected", flush=True)

    # 当前页快照
    ocr, texts = dump_state(client, "start")

    joined = " ".join(texts)

    # 书架页 → 点底部 tab（推荐/精选）离开书架
    if "书架" in joined and "阅读时长" not in joined:
        if not tap_text(client, ocr, "推荐"):
            if not tap_text(client, ocr, "精选"):
                # 兜底：底部第二个 tab 坐标 (216, 1235)
                print("[nav] 兜底点击底部tab (216,1235)")
                client.click(216, 1235)
                time.sleep(2.5)
        ocr, texts = dump_state(client, "tab2")
        joined = " ".join(texts)

    # 找奖励入口卡片（本周阅读时长 / 领赠币）
    for attempt in range(3):
        if "阅读时长" in joined or "领赠币" in joined or "赠币" in joined:
            break
        # 没看到就翻一屏
        client.swipe(360, 900, 360, 500, 400)
        time.sleep(1.5)
        ocr, texts = dump_state(client, f"scan{attempt}")
        joined = " ".join(texts)

    for kw in ("本周阅读时长", "阅读时长", "领赠币", "赠币"):
        if tap_text(client, ocr, kw):
            break
    time.sleep(3.5)
    ocr, texts = dump_state(client, "reward")

    # 奖励页 → 滚到游戏卡 → 终态判定
    client.swipe(360, 1000, 360, 400, 400)
    time.sleep(1.0)
    client.swipe(360, 1000, 360, 400, 400)
    time.sleep(2.0)
    dump_state(client, "game_card")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
