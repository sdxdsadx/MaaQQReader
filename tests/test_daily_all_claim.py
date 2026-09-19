from scripts.daily_all import _find_nearby_claim


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
