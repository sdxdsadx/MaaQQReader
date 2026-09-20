from scripts.daily_all import (
    _audiobook_reward_done,
    _find_audiobook_float_close,
    _find_nearby_claim,
    _find_shelf_reward_entry,
)


def test_find_nearby_claim_accepts_short_and_long_button_copy() -> None:
    boxes = [
        ("每日听书30分钟+20赠币", (60, 600, 260, 40)),
        ("领取", (540, 610, 100, 44)),
        ("立即领取", (540, 900, 100, 44)),
    ]

    assert _find_nearby_claim(boxes) == ("领取", (540, 610, 100, 44))


def test_find_nearby_claim_ignores_unrelated_claim_button() -> None:
    boxes = [
        ("每日听书30分钟+20赠币", (60, 600, 260, 40)),
        ("立即领取", (540, 900, 100, 44)),
    ]

    assert _find_nearby_claim(boxes) is None


def test_find_audiobook_float_close_prefers_left_bottom_x() -> None:
    boxes = [
        ("X", (186, 1112, 20, 24)),
        ("X", (610, 1050, 20, 24)),
        ("书架", (35, 50, 70, 35)),
    ]

    assert _find_audiobook_float_close(boxes) == ("X", (186, 1112, 20, 24))


def test_find_shelf_reward_entry_accepts_dynamic_coin_amount() -> None:
    boxes = [
        ("领250赠币", (527, 161, 132, 44)),
        ("全职法师", (138, 590, 130, 40)),
        ("今日已获赠币324", (200, 900, 200, 40)),
    ]

    assert _find_shelf_reward_entry(boxes) == ("领250赠币", (527, 161, 132, 44))


def test_audiobook_reward_done_is_scoped_to_audiobook_card() -> None:
    boxes = [
        ("每日听书30分钟+20赠币", (60, 724, 260, 36)),
        ("明日再来", (550, 738, 90, 32)),
        ("每日阅读领赠币", (60, 280, 220, 36)),
    ]

    assert _audiobook_reward_done(boxes) is True
