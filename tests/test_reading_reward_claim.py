from qqreader.tasks.reading_reward import (
    parse_coin_total,
    reading_claim_buttons,
    reading_rewards_complete,
)


def test_reading_claim_buttons_are_limited_to_reading_card():
    boxes = (
        ("每日阅读领赠币", (60, 360, 220, 40)),
        ("领取", (190, 580, 70, 35)),
        ("立即领取", (470, 580, 120, 35)),
        ("每日听书30分钟+20赠币", (60, 800, 300, 40)),
        ("立即领取", (520, 820, 120, 35)),
    )

    assert reading_claim_buttons(boxes) == boxes[1:3]


def test_complete_requires_reading_card_claim_evidence():
    boxes = (
        ("每日阅读领赠币", (60, 360, 220, 40)),
        ("今日任务已完成", (60, 400, 220, 40)),
        ("已领取", (190, 580, 70, 35)),
        ("已领取", (470, 580, 70, 35)),
        ("每日听书30分钟+20赠币", (60, 800, 300, 40)),
    )

    assert reading_rewards_complete(boxes) is True


def test_coin_total_is_parsed():
    assert parse_coin_total((("今日已获赠币254", (0, 0, 1, 1)),)) == 254
