"""根据奖励卡片证据生成剩余时长计划。"""
from __future__ import annotations

import math
import re
import time
from pathlib import Path

from .task_catalog import default_settings, save_task_settings
from ..reward.nav import goto_reward_page

MARKERS = {
    "DailyReadingFlow": "每日阅读",
    "WeeklyReading": "每周阅读600",
    "DailyAudiobookFlow": "每日听书",
    "DailyGameFlow": "玩游戏领赠币",
    "DailyAdFlow": "看小视频领好礼",
}


def _normalized_ocr(text: str) -> str:
    """Normalize a small set of observed, unambiguous reward-page OCR errors."""
    return text.replace(" ", "").replace("赠市", "赠币")


def _has_daily_reading_card(boxes) -> bool:
    return any("每日阅读领赠币" in _normalized_ocr(text) for text, _ in boxes)


def _dismiss_checkin_popup(client, boxes) -> bool:
    if not any("签到成功" in text for text, _ in boxes):
        return False
    button = next((box for text, box in boxes if "我知道了" in text), None)
    if button is None:
        return False
    x, y, width, height = button
    client.click(x + width // 2, y + height // 2)
    time.sleep(1)
    return True


def plan_from_cards(cards):
    settings = default_settings()
    for setting in settings.values():
        setting.enabled = False
    notes = []
    reading = []
    for key, marker in MARKERS.items():
        text = cards.get(key, "").replace(" ", "")
        if not text:
            notes.append(f"{marker}：未识别，待确认")
            continue
        if "明日再来" in text or "已领取" in text or "今日已领" in text:
            # Reading has multiple tiers; a single claimed tier is insufficient.
            if key != "DailyReadingFlow" or "明日再来" in text or "今日已领40" in text or text.count("已领取") >= 2:
                notes.append(f"{marker}：已领取")
                continue
        if key == "DailyAdFlow":
            counter = re.search(r"(\d+)/12", text)
            if counter:
                settings[key].enabled = int(counter[1]) < 12
                notes.append(f"{marker}：{counter[1]}/12")
            else:
                notes.append(f"{marker}：次数未识别，待确认")
            continue
        match = re.search(r"(?:再读|再听|再玩|还需|还差|剩余)(\d+(?:\.\d+)?)分钟", text)
        if match:
            missing = float(match[1])
            if key == "DailyReadingFlow":
                # The page can describe the next 10-minute tier, not the final tier.
                tier = re.search(r"再读\d+分钟领", text)
                if tier and missing <= 10:
                    missing += 20
            if key in {"DailyReadingFlow", "WeeklyReading"}:
                reading.append(missing)
            else:
                settings[key].enabled = True
                field = "duration_minutes" if key == "DailyGameFlow" else "minutes"
                settings[key].values.update({field: missing + 5, "count": 1, "timeout_minutes": missing + 20})
            notes.append(f"{marker}：缺少{missing:g}分钟，追加5分钟")
        elif key == "DailyGameFlow" and "任一在线游戏20分钟" in text and "去玩游戏" in text:
            settings[key].enabled = True
            settings[key].values.update(duration_minutes=25, count=1)
            notes.append("游戏：页面要求20分钟，计划25分钟")
        elif "立即领取" in text:
            if key == "DailyReadingFlow":
                settings["ClaimOneReward"].enabled = True
            elif key == "DailyAudiobookFlow":
                settings["ClaimAudiobookReward"].enabled = True
            notes.append(f"{marker}：可领取，时长无需追加")
        else:
            notes.append(f"{marker}：剩余时长未确认")
    if reading:
        total = max(reading) + 5
        count = max(1, math.ceil(total / 120))
        settings["DailyReadingFlow"].enabled = True
        settings["DailyReadingFlow"].values.update(count=count, minutes=total / count, timeout_minutes=total / count + 15)
    notes.append("等级广告：奖励页无法确认等级卡状态，保持未选择")
    return settings, notes


def collect_cards(client, evidence_dir: Path):
    if not goto_reward_page(client):
        raise RuntimeError("未确认奖励页，无法规划")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    cards = {}
    # First return to top, then inspect each viewport before scrolling further.
    for _ in range(10):
        shot = client.screencap()
        boxes = client.recognize("OCR", {}, shot).text_boxes()
        if any("安全验证" in t or "完成拼图" in t for t, _ in boxes):
            raise RuntimeError("验证码阻塞规划，请先处理")
        if _dismiss_checkin_popup(client, boxes):
            continue
        if _has_daily_reading_card(boxes):
            break
        client.swipe(360, 350, 360, 1100, 500)
        time.sleep(1)
    else:
        raise RuntimeError("未回到每日阅读卡片，保留原计划，请重试规划")
    pages = []
    for index in range(9):
        shot = client.screencap()
        shot.save(evidence_dir / f"page_{index}.png")
        boxes = client.recognize("OCR", {}, shot).text_boxes()
        pages.append(boxes)
        if any("安全验证" in t or "完成拼图" in t for t, _ in boxes):
            raise RuntimeError("验证码阻塞规划，请先处理")
        for key, marker in MARKERS.items():
            anchor = next((b for t, b in boxes if marker in _normalized_ocr(t)), None)
            if anchor is None:
                continue
            height = 330 if key == "DailyReadingFlow" else 100
            text = " ".join(t for t, b in sorted(boxes, key=lambda item: item[1][1]) if anchor[1]-5 <= b[1] < min(anchor[1]+height, 1200))
            if len(text) > len(cards.get(key, "")):
                cards[key] = text
        if index < 8:
            client.swipe(360, 1100, 360, 650, 450)
            time.sleep(1)
    return cards, pages
