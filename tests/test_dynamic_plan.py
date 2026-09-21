from qqreader.gui.dynamic_plan import plan_from_cards


def test_remaining_time_gets_one_buffer_and_completed_ads_are_skipped():
    settings, _ = plan_from_cards({
        "DailyAudiobookFlow": "每日听书30分钟 再听12分钟即可获得",
        "DailyAdFlow": "看小视频领好礼 (12/12)",
        "WeeklyReading": "每周阅读600分钟 再读250分钟即可获得",
    })
    assert settings["DailyAudiobookFlow"].values["minutes"] == 17
    assert not settings["DailyAdFlow"].enabled
    reading = settings["DailyReadingFlow"].values
    assert reading["count"] * reading["minutes"] == 255


def test_unknown_does_not_mean_completed_or_start_default_duration():
    settings, notes = plan_from_cards({})
    assert not any(s.enabled for s in settings.values())
    assert any("待确认" in note for note in notes)


def test_next_reading_tier_accounts_for_final_thirty_minute_tier():
    settings, _ = plan_from_cards({"DailyReadingFlow": "每日阅读领赠币 今日再读6分钟领20赠币"})
    assert settings["DailyReadingFlow"].values["minutes"] == 31


def test_live_game_remaining_and_completed_daily_reading():
    settings, _ = plan_from_cards({
        "DailyReadingFlow": "每日阅读领赠币 明日再来 今日任务已完成 领取 领取",
        "DailyGameFlow": "玩游戏领赠币 去玩游戏 再玩19分钟即可领取",
    })
    assert not settings["DailyReadingFlow"].enabled
    assert settings["DailyGameFlow"].values["duration_minutes"] == 24


def test_completed_listening_only_schedules_claim():
    settings, _ = plan_from_cards({"DailyAudiobookFlow": "每日听书30分钟 立即领取 已听83分钟"})
    assert settings["ClaimAudiobookReward"].enabled
    assert not settings["DailyAudiobookFlow"].enabled
