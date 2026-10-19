"""Issue #11 诊断: 点「去玩游戏」后的真实流向 + 领取按钮文案/位置 + 赠币计数变化。

流程（全程不使用下拉刷新手势）:
  1. 导航到奖励页（书架→底部tab→奖励卡；已在此页则跳过）
  2. 读「今日已获赠币N」基线
  3. 滚到游戏卡区，dump 所有 OCR 框(y 排序)，点第一张卡的「去玩游戏」
  4. 等 15s → 截图+OCR dump（确认流入哪个页面）
  5. BACK → 3s → 截图+OCR dump
  6. 小步滚回顶部读计数器（避免触发刷新），再滚下去找「立即领取/已领取/明日再来」
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config  # noqa: E402
from qqreader.maa.factory import build_maa_client  # noqa: E402

SHOT_DIR = _ROOT / "runtime" / "screenshots"

KEY_WORDS = (
    "去玩游戏", "立即领取", "已领取", "明日再来", "今日已获赠币",
    "回到顶部", "获奖记录", "在线玩", "玩游戏领赠币", "书架",
    "灵画师", "守吾王座", "阅读时长",
)


def iter_boxes(ocr):
    """yield (text, cx, cy) — 实测 detail 结构: {"all": [{"box":[x,y,w,h], "text":...}]}"""
    detail = ocr.detail if isinstance(ocr.detail, dict) else {}
    items = detail.get("all") or detail.get("boxes") or detail.get("items") or []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        txt = str(it.get("text", ""))
        box = it.get("box")
        if not box or len(box) < 4:
            continue
        x, y, w, h = box[0], box[1], box[2], box[3]
        out.append((txt, x + w / 2.0, y + h / 2.0))
    return out


def dump_state(client, tag):
    shot = client.screencap()
    out = SHOT_DIR / f"probe11_{tag}.png"
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_bytes(shot.data if hasattr(shot, "data") else shot)
    ocr = client.recognize("OCR", {}, shot)
    boxes = iter_boxes(ocr)
    texts = list(ocr.all_texts()) if (ocr.hit or ocr.detail) else []
    hits = [t for t in texts if any(k in t for k in KEY_WORDS)]
    print(f"\n===== [{tag}] screenshot={out.name} 命中 {len(hits)}/{len(texts)} =====")
    for h in hits:
        print("  HIT:", h)
    ysorted = sorted(boxes, key=lambda b: b[2])
    print(f"  boxes({len(ysorted)}):")
    for txt, cx, cy in ysorted:
        print(f"    y={cy:6.0f} x={cx:5.0f} | {txt[:44]}")
    return texts, boxes


def read_counter(texts):
    joined = "".join(texts)
    m = re.search(r"今日已获赠币\s*([0-9０-９]+)", joined)
    if m:
        return m.group(1)
    return None


def find_box(boxes, keyword):
    for txt, cx, cy in boxes:
        if keyword in txt:
            return (cx, cy, txt)
    return None


def ensure_reward_page(client):
    """导航到奖励页；已在则不动。返回 True=在奖励页。"""
    seen_reward_cards = 0
    for attempt in range(7):
        texts, boxes = dump_state(client, f"nav{attempt}")
        joined = "".join(texts)
        if ("玩游戏领赠币" in joined or "去玩游戏" in joined
                or "今日已获赠币" in joined or "获奖记录" in joined):
            print("[nav] 已在奖励页")
            return True
        # 书城信息流 → 先回书架 tab（tab 栏固定: 书架89/书城269/发现449/我的629）
        bottom_tabs = [b for b in boxes if b[2] > 1200 and
                       any(t in b[0] for t in ("书架", "书城", "发现", "我的"))]
        on_bookstore = any(k in joined for k in ("今日必读", "本周强推", "潜力新书",
                                                 "完本精选", "会员榜", "100万+好书"))
        if on_bookstore and bottom_tabs:
            shelf_tab = next((b for b in bottom_tabs if "书架" in b[0]), None)
            if shelf_tab:
                print(f"[nav] 书城→点书架tab @({shelf_tab[1]:.0f},{shelf_tab[2]:.0f})")
                client.click(int(shelf_tab[1]), int(shelf_tab[2]))
                time.sleep(3.0)
                continue
        # 主页(书架) → 点「本周阅读时长」奖励卡（home_ocr_reward_entry 同源）
        for kw in ("本周阅读时长", "再读", "阅读时长", "领赠币"):
            hit = find_box(boxes, kw)
            if hit:
                print(f"[nav] 书架→点奖励卡 {hit[2]!r} @({hit[1]:.0f},{hit[2]:.0f})")
                client.click(int(hit[1]), int(hit[2]))
                time.sleep(3.5)
                break
        else:
            if "书架" in joined and not on_bookstore:
                # 奖励卡在书架顶部(≈y196)；当前列表不可滚动时用下拉刷新唤出
                # （书架是原生页，下拉刷新安全；H5 奖励页才禁止刷新）。
                if seen_reward_cards >= 1:
                    print("[nav] 书架已滚动仍无奖励卡 → 下拉刷新唤出顶部奖励卡")
                    client.swipe(360, 350, 360, 1100, 500)
                    time.sleep(3.0)
                else:
                    print("[nav] 书架未见奖励卡 → 点顶部横幅位 (173,196)")
                    client.click(173, 196)
                    time.sleep(3.0)
                    seen_reward_cards += 1
            else:
                print("[nav] 未识别页面，下滑一屏找")
                client.swipe(360, 900, 360, 420, 400)
                time.sleep(1.5)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--skip-entry", action="store_true",
                        help="只观察当前奖励页，不点「去玩游戏」")
    args = parser.parse_args()

    config = load_config(args.config)
    client = build_maa_client(config)
    client.connect()
    print("[probe] connected", flush=True)

    try:
        # 兜底: 若卡在阅读页(之前误点书) → BACK 退出
        texts, _ = dump_state(client, "start")
        if "上午" in "".join(texts) or "第1章" in "".join(texts):
            print("[nav] 检测到阅读页, BACK 退出")
            client.click_key(4)
            time.sleep(2.0)
        if not ensure_reward_page(client):
            print("[probe] FATAL: 未能到达奖励页")
            return 2

        # --- 基线计数器（应在页面顶部可见）---
        texts, boxes = dump_state(client, "reward_top")
        counter_before = read_counter(texts)
        print(f"\n>>> COUNTER_BEFORE = {counter_before}")

        if args.skip_entry:
            return 0

        # --- 滚到游戏卡区 ---
        client.swipe(360, 1000, 360, 420, 400)
        time.sleep(1.2)
        texts, boxes = dump_state(client, "game_card")
        joined = "".join(texts)
        if "去玩游戏" not in joined:
            client.swipe(360, 1000, 360, 420, 400)
            time.sleep(1.2)
            texts, boxes = dump_state(client, "game_card2")
            joined = "".join(texts)

        btn = find_box(boxes, "去玩游戏")
        if not btn:
            print("[probe] FATAL: 游戏卡区未见「去玩游戏」")
            return 3
        print(f"\n>>> 目标按钮 去玩游戏 @({btn[0]:.0f},{btn[1]:.0f}) text={btn[2]!r}")

        # --- 点「去玩游戏」→ 15s → dump ---
        client.click(int(btn[0]), int(btn[1]))
        time.sleep(15.0)
        texts_after_tap, _ = dump_state(client, "after_tap")
        joined_tap = "".join(texts_after_tap)
        verdict_tap = []
        for kw in ("在线玩", "游戏大厅", "进入游戏", "登录游戏", "立即领取",
                   "去玩游戏", "获奖记录", "今日已获赠币", "回到顶部"):
            if kw in joined_tap:
                verdict_tap.append(kw)
        print(f"\n>>> after_tap 关键词: {verdict_tap}")

        # --- BACK → 3s → dump ---
        client.click_key(4)
        time.sleep(3.0)
        texts_back, boxes_back = dump_state(client, "after_back")
        joined_back = "".join(texts_back)
        print("\n>>> after_back 关键词命中:",
              [k for k in ("立即领取", "已领取", "明日再来", "去玩游戏",
                           "今日已获赠币", "回到顶部", "书架") if k in joined_back])

        # --- 小步滚回顶部读计数器（500→950，避免触发下拉刷新）---
        counter_after = None
        for i in range(3):
            texts_top, _ = dump_state(client, f"back_top{i}")
            counter_after = read_counter(texts_top)
            if counter_after:
                break
            if "书架" in "".join(texts_top):
                print("[probe] WARN: 意外离开奖励页，停止上滚")
                break
            client.swipe(360, 500, 360, 950, 350)
            time.sleep(1.0)
        print(f"\n>>> COUNTER_AFTER = {counter_after}  (before={counter_before})")

        # --- 再滚下去找领取相关按钮 ---
        claim_seen = []
        for i in range(3):
            texts_dn, _ = dump_state(client, f"claim_scan{i}")
            joined_dn = "".join(texts_dn)
            for kw in ("立即领取", "已领取", "明日再来"):
                if kw in joined_dn and kw not in claim_seen:
                    claim_seen.append(kw)
            if claim_seen or "回到顶部" in joined_dn:
                break
            client.swipe(360, 980, 360, 420, 400)
            time.sleep(1.2)
        print(f"\n>>> CLAIM_TEXTS_SEEN = {claim_seen}")
        print("\n>>> DONE: COUNTER_BEFORE=%s COUNTER_AFTER=%s CLAIM=%s"
              % (counter_before, counter_after, claim_seen))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
