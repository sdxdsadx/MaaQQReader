"""每日阅读奖励的定向领取与结果验证。"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from ..maa.client import Box, MaaClient

TextBox = tuple[str, Box]
COIN_PATTERN = re.compile(r"今日已获赠币\s*(\d+)")


@dataclass(frozen=True)
class ReadingRewardClaimResult:
    succeeded: bool
    reason: str
    before_coins: int | None = None
    after_coins: int | None = None
    clicked: int = 0
    before_screenshot: Path | None = None
    after_screenshot: Path | None = None


def parse_coin_total(boxes: Iterable[TextBox]) -> int | None:
    for text, _box in boxes:
        match = COIN_PATTERN.search(text.replace(" ", ""))
        if match:
            return int(match.group(1))
    return None


def reading_card_bounds(boxes: Sequence[TextBox]) -> tuple[int, int] | None:
    # 2026-09-25 的 Maa OCR 把卡片标题末字“币”连续读成“市”。
    card = next(
        (box for text, box in boxes if re.search(r"每日阅读领赠[币市]", text)),
        None,
    )
    if card is None:
        return None
    top = card[1]
    following = [
        box[1]
        for text, box in boxes
        if box[1] > top and any(marker in text for marker in ("每日听书", "每周5天听书"))
    ]
    return top, min(following) if following else min(1280, top + 460)


def reading_claim_buttons(boxes: Sequence[TextBox]) -> tuple[TextBox, ...]:
    bounds = reading_card_bounds(boxes)
    if bounds is None:
        return ()
    top, bottom = bounds
    return tuple(
        (text, box)
        for text, box in boxes
        if text.strip() in {"领取", "立即领取"} and top < box[1] < bottom
    )


def reading_rewards_complete(boxes: Sequence[TextBox]) -> bool:
    bounds = reading_card_bounds(boxes)
    if bounds is None:
        return False
    top, bottom = bounds
    texts = [text for text, box in boxes if top <= box[1] < bottom]
    joined = " ".join(texts)
    claimed_count = sum(text.strip() == "已领取" for text in texts)
    return (
        "今日已领40赠币" in joined
        or ("今日任务已完成" in joined and claimed_count >= 2)
        or claimed_count >= 2
    )


def _boxes(client: MaaClient) -> tuple[TextBox, ...]:
    shot = client.screencap()
    return client.recognize("OCR", {}, shot).text_boxes()


def _click_box(client: MaaClient, box: Box) -> None:
    x, y, width, height = box
    client.click(x + width // 2, y + height // 2)


def _is_reward_page(boxes: Sequence[TextBox]) -> bool:
    text = " ".join(item[0] for item in boxes)
    return "今日已获赠币" in text or "每日阅读领赠币" in text


def _open_reward_page(client: MaaClient) -> tuple[TextBox, ...]:
    client.start_app("com.qq.reader")
    time.sleep(3)
    for _ in range(7):
        boxes = _boxes(client)
        if _is_reward_page(boxes):
            return boxes
        entry = next(
            (
                box
                for text, box in boxes
                if "兑赠币" in text
                or "领20赠币" in text
                or ("本周" in text and "阅读" in text)
            ),
            None,
        )
        if entry is not None:
            _click_box(client, entry)
            time.sleep(5)
            continue
        client.click_key(4)
        time.sleep(1.2)
    raise RuntimeError("无法从当前页面进入阅读奖励页")


def _show_reading_card(client: MaaClient) -> tuple[TextBox, ...]:
    for _ in range(10):
        boxes = _boxes(client)
        if reading_card_bounds(boxes) is not None:
            return boxes
        go_top = next((box for text, box in boxes if text.strip() == "回到顶部"), None)
        if go_top is not None:
            _click_box(client, go_top)
        else:
            client.swipe(360, 300, 360, 1100, 500)
        time.sleep(1.2)
    raise RuntimeError("奖励页未找到“每日阅读领赠币”卡片")


def reading_card_texts(boxes: Sequence[TextBox]) -> tuple[str, ...]:
    """奖励页“每日阅读领赠币”卡片内的 OCR 文案（用于失败诊断）。"""
    bounds = reading_card_bounds(boxes)
    if bounds is None:
        return ()
    top, bottom = bounds
    return tuple(text for text, box in boxes if top <= box[1] < bottom)


def _save_evidence(client: MaaClient, path: Path) -> None:
    """保存固定名证据，同时另存一份带时间戳的副本，避免下一次运行覆盖。"""
    image = client.screencap()
    image.save(path)
    stamped = path.with_name(
        f"{path.stem}_{time.strftime('%Y%m%d_%H%M%S')}{path.suffix}"
    )
    try:
        image.save(stamped)
    except Exception:  # noqa: BLE001 - 副本失败不影响领取结果
        pass


def _refresh_reward_page(client: MaaClient) -> tuple[TextBox, ...]:
    """返回再进入奖励页，让服务器同步后的阅读时长重新渲染。"""
    client.click_key(4)
    time.sleep(1.5)
    _open_reward_page(client)
    return _show_reading_card(client)


def claim_reading_rewards(
    client: MaaClient,
    screenshot_dir: Path,
    *,
    evidence_prefix: str = "reading_reward_claim",
    sync_retries: int = 3,
    sync_wait_seconds: float = 20.0,
) -> ReadingRewardClaimResult:
    """领取每日阅读 10/30 分钟两档奖励，并用页面状态或币值增长验收。

    阅读刚结束时服务器可能还没同步阅读时长，此时两档按钮都不可领。
    2026-09-23 实测第 1 次 35 分钟阅读结束约 30 秒后领取即失败，第 2 次
    同一张卡两档都可领。因此没有可领按钮时，等待并刷新奖励页再判定。
    """
    screenshot_dir = Path(screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    _open_reward_page(client)
    boxes = _show_reading_card(client)
    for _ in range(max(0, int(sync_retries))):
        if reading_rewards_complete(boxes) or reading_claim_buttons(boxes):
            break
        print(
            "[reading-reward] 阅读奖励暂不可领，等待时长同步后刷新："
            + " / ".join(reading_card_texts(boxes)),
            flush=True,
        )
        time.sleep(float(sync_wait_seconds))
        boxes = _refresh_reward_page(client)
    before_path = screenshot_dir / f"{evidence_prefix}_before.png"
    _save_evidence(client, before_path)
    before = parse_coin_total(boxes)

    if reading_rewards_complete(boxes):
        return ReadingRewardClaimResult(
            True,
            "每日阅读奖励已领取，无需重复点击",
            before,
            before,
            before_screenshot=before_path,
            after_screenshot=before_path,
        )

    clicked = 0
    for _ in range(3):
        buttons = reading_claim_buttons(boxes)
        if not buttons:
            break
        _click_box(client, buttons[0][1])
        clicked += 1
        time.sleep(2)
        boxes = _show_reading_card(client)
        if reading_rewards_complete(boxes):
            break

    after_path = screenshot_dir / f"{evidence_prefix}_after.png"
    _save_evidence(client, after_path)
    after = parse_coin_total(boxes)
    complete = reading_rewards_complete(boxes)
    grew = before is not None and after is not None and after > before
    if complete or grew:
        detail = "页面显示已领取" if complete else f"赠币 {before} → {after}"
        return ReadingRewardClaimResult(
            True,
            f"每日阅读奖励领取成功：{detail}",
            before,
            after,
            clicked,
            before_path,
            after_path,
        )
    return ReadingRewardClaimResult(
        False,
        "每日阅读奖励未达到可领取状态，或点击后缺少币值/已领取证据；卡片文案："
        + (" / ".join(reading_card_texts(boxes)) or "<未识别到阅读卡>"),
        before,
        after,
        clicked,
        before_path,
        after_path,
    )
