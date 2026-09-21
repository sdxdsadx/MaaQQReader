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
        "AdCountdown",
        "AdStaticDownloadPage",
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
