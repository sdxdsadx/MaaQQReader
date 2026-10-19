import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_task  # noqa: E402


def test_level_ad_overrides_recover_from_bottom_and_static_download_ads() -> None:
    data = {
        "LevelPageReady": {"next": ["LevelClickCoinAd"]},
        "LevelClickCoinAd": {"next": ["AdCountdown", "AdScrollDownRepeat"]},
        "LevelClickPointsAd": {"next": ["AdCountdown", "AdScrollDownRepeat"]},
        "LevelPointsSectionFound": {
            "recognition": "OCR",
            "expected": "看小视频.*[+＋]5积分",
        },
        "AdRewardIssued": {"next": ["AdClosableAfterCountdown"]},
    }

    run_task._apply_level_ad_runtime_overrides(data)

    assert data["LevelPageReady"]["next"] == ["LevelTopReady", "LevelScrollToTop"]
    assert data["LevelScrollToTop"]["end"] == [360, 1120]
    assert data["AdStaticDownloadWait"]["post_delay"] == 35000
    assert data["LevelClickCoinAd"]["next"] == [
        # 2026-10-19：「暂无可播视频」弹窗先于“仍在等级页”的等待和重新点击。
        "LevelAdNoVideoDialog",
        "AdCountdown",
        "AdStaticDownloadPage",
        "LevelCoinAdNotStarted",
        "AdScrollDownRepeat",
    ]
    assert data["AdRewardIssued"]["next"][0] == "AdReturnedAfterClose"
    assert data["LevelPointsSectionFound"]["expected"] == "^今日已完成$"
    assert data["LevelPointsSectionFound"]["roi"] == [520, 500, 180, 300]


def test_level_ad_overrides_are_idempotent() -> None:
    data = {
        "LevelPageReady": {"next": []},
        "LevelClickCoinAd": {"next": ["AdScrollDownRepeat"]},
        "LevelClickPointsAd": {"next": ["AdScrollDownRepeat"]},
        "LevelPointsSectionFound": {"recognition": "OCR"},
        "AdRewardIssued": {"next": ["AdClosableAfterCountdown"]},
    }

    run_task._apply_level_ad_runtime_overrides(data)
    run_task._apply_level_ad_runtime_overrides(data)

    assert data["LevelClickCoinAd"]["next"].count("AdStaticDownloadPage") == 1
    assert data["AdRewardIssued"]["next"].count("AdReturnedAfterClose") == 1


def _level_pipeline() -> dict:
    return {
        "AdSlideCaptchaDetected": {},
        "AdCaptchaDetected": {},
        "LevelPageReady": {"next": []},
        "LevelMyPageReady": {"next": ["LevelClickLevelIcon"]},
        "LevelClickLevelIcon": {
            "recognition": "OCR", "expected": "^等级$", "action": "Click",
            "next": ["LevelPageReady"],
        },
        "LevelClickCoinAd": {
            "recognition": "OCR", "expected": "^立即领取$", "action": "Click",
            "anchor": {"LevelAfterAd": "LevelAfterCoinAd"},
            "next": ["AdCountdown", "AdScrollDownRepeat"],
        },
        "LevelClickPointsAd": {
            "recognition": "OCR", "expected": "^看小视频$", "action": "Click",
            "anchor": {"LevelAfterAd": "LevelAfterPointsAd"},
            "next": ["AdCountdown", "AdScrollDownRepeat"],
        },
        "LevelPointsSectionFound": {"recognition": "OCR"},
        "AdRewardIssued": {"next": []},
    }


def test_level_icon_click_swallowed_retries_without_global_ocr_x_close() -> None:
    """2026-09-23 20:30：「等级」点击被吞后必须重点；不能按全屏 OCR “X” 关弹窗
    （「我的」页「基因」图标会被读成 X，2026-09-24 验证时误入阅读基因页）。"""
    data = _level_pipeline()
    run_task._apply_level_ad_runtime_overrides(data)

    assert data["LevelClickLevelIcon"]["next"] == [
        *run_task.LEVEL_CAPTCHA_NODES, "LevelPromoVisible",
        "LevelPageReady", "LevelTeenModeDismiss", "LevelClickLevelIconAgain",
    ]
    assert data["LevelMyPageReady"]["next"][3] == "LevelTeenModeDismiss"
    assert "LevelMyPopupClose" not in data
    assert all(
        "X" not in str(node.get("expected", ""))
        for name, node in data.items()
        # 这两个 X 节点都要先确认弹窗文字（月票活动 / 暂无可播视频），且只看弹窗底部窄 ROI。
        if name.startswith("Level") and name not in ("LevelPromoClose", "LevelAdNoVideoClose")
        and isinstance(node, dict)
    )
    assert data["LevelAdNoVideoClose"]["roi"] == [260, 940, 200, 140]
    assert data["LevelAdNoVideoDialog"]["next"][len(run_task.LEVEL_CAPTCHA_NODES)] == "LevelAdNoVideoClose"
    assert data["LevelPromoClose"]["roi"] == [300, 870, 120, 170]
    assert data["LevelPromoVisible"]["next"] == [*run_task.LEVEL_CAPTCHA_NODES, "LevelPromoClose"]
    assert data["LevelClickLevelIconAgain"]["max_hit"] == 3
    for name in ("LevelTeenModeDismiss", "LevelClickLevelIconAgain"):
        for ref in data[name]["next"]:
            assert ref in data


def test_level_ad_not_launched_waits_then_reclicks_instead_of_scrolling() -> None:
    """2026-09-23 18:16：广告未拉起时不能把等级页当广告去下滑。"""
    data = _level_pipeline()
    run_task._apply_level_ad_runtime_overrides(data)

    points_next = data["LevelClickPointsAd"]["next"]
    assert points_next.index("LevelPointsAdNotStarted") < points_next.index(
        "AdScrollDownRepeat"
    )
    wait = data["LevelPointsAdNotStarted"]
    assert wait["action"] == "DoNothing" and wait["max_hit"] == 4
    assert wait["next"].index("LevelClickPointsAdAgain") < wait["next"].index(
        "AdScrollDownRepeat"
    )
    again = data["LevelClickPointsAdAgain"]
    assert again["expected"] == "^看小视频$"
    assert again["anchor"] == {"LevelAfterAd": "LevelAfterPointsAd"}
    assert again["max_hit"] == 2

    run_task._apply_level_ad_runtime_overrides(data)
    assert data["LevelClickPointsAd"]["next"].count("LevelPointsAdNotStarted") == 1


def test_points_ad_abandoned_browse_offer_retries_with_another_ad() -> None:
    """2026-09-24：积分广告为浏览型被跳过放弃，返回后应换一条广告重试。"""
    data = _level_pipeline()
    data["LevelAfterPointsAd"] = {"next": []}
    run_task._apply_level_ad_runtime_overrides(data)

    for name in ("LevelAfterPointsAd", "LevelVerifyPointsScroll"):
        nxt = data[name]["next"]
        assert nxt[:len(run_task.LEVEL_CAPTCHA_NODES)] == list(run_task.LEVEL_CAPTCHA_NODES)
        assert nxt[len(run_task.LEVEL_CAPTCHA_NODES)] == "LevelPointsSectionFound"
        assert nxt.index("LevelClickPointsAdAgain") < nxt.index("LevelVerifyPointsScroll")
    assert data["LevelClickPointsAdAgain"]["max_hit"] == 2
