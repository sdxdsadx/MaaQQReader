"""MaaFramework 适配层单元测试（假客户端，无需 DLL/设备）。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pytest

from qqreader.config import default_config, loads_config
from qqreader.maa import (
    FeatureCatalog,
    MaaClientError,
    MaaDeviceController,
    MaaFeatureLocator,
    MaaPageObserver,
    RecoResult,
    Screenshot,
    build_maa_client,
    build_maa_runtime,
    parse_foreground_package,
    run_doctor,
)
from qqreader.page.features import FeatureKind
from qqreader.page.states import Orientation
from qqreader.tasks import AD_TASK_NAME, GAME_TASK_NAME

# 仅用于构造 Screenshot 的占位字节；测试不解码图片。
FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class FakeMaaClient:
    def __init__(
        self,
        screenshots: Optional[Sequence[Screenshot]] = None,
        recognizer: Optional[Any] = None,
    ) -> None:
        self._screenshots = list(screenshots or [Screenshot(FAKE_PNG, 720, 1280)])
        self._index = 0
        self._recognizer = recognizer or (
            lambda reco_type, params, shot: RecoResult.miss(reco_type)
        )
        self.clicks: List[Tuple[int, int]] = []
        self.swipes: List[Tuple[int, int, int, int, int]] = []
        self.keys: List[int] = []
        self.started: List[str] = []
        self.stopped: List[str] = []
        self.recognitions: List[Tuple[str, Dict[str, Any]]] = []
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.connected = False

    def screencap(self) -> Screenshot:
        shot = self._screenshots[self._index % len(self._screenshots)]
        self._index += 1
        return shot

    def click(self, x: int, y: int) -> bool:
        self.clicks.append((x, y))
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        self.swipes.append((x1, y1, x2, y2, duration_ms))
        return True

    def click_key(self, keycode: int) -> bool:
        self.keys.append(keycode)
        return True

    def start_app(self, package: str) -> bool:
        self.started.append(package)
        return True

    def stop_app(self, package: str) -> bool:
        self.stopped.append(package)
        return True

    def recognize(
        self, reco_type: str, params: Mapping[str, Any], screenshot: Screenshot
    ) -> RecoResult:
        self.recognitions.append((reco_type, dict(params)))
        return self._recognizer(reco_type, params, screenshot)


class FakeLocator:
    def __init__(self, centers: Mapping[str, Optional[Tuple[int, int]]]) -> None:
        self._centers = dict(centers)

    def locate(self, key: str):
        center = self._centers.get(key)
        return None if center is None else (center[0], center[1], 1, 1)

    def center(self, key: str):
        return self._centers.get(key)


class FakeProbe:
    def probe(self):
        return "com.qq.reader"

    def is_installed(self, package: str):
        return True


def test_catalog_classifies_feature_keys() -> None:
    catalog = FeatureCatalog.from_feature_keys()
    assert catalog.require("home_ocr_shelf").kind is FeatureKind.OCR
    assert catalog.require("home_nav_my").kind is FeatureKind.ICON
    assert catalog.require("game_exit_dialog").kind is FeatureKind.TEMPLATE
    assert catalog.require("reward_bottom_nav").kind is FeatureKind.STRUCTURE
    assert catalog.require("qq_reader_package").kind is FeatureKind.CURRENT_APP
    # 正则只给识别器用，不作为可定位资源。
    assert all(not key.endswith("_regex") for key in catalog.assets)


def test_device_controller_maps_actions() -> None:
    client = FakeMaaClient()
    device = MaaDeviceController(client)
    device.tap_point(10, 20)
    device.swipe(1, 2, 3, 4, 500)
    device.press_back()
    device.launch_app("com.qq.reader")
    device.stop_app("com.qq.reader")

    assert client.clicks == [(10, 20)]
    assert client.swipes == [(1, 2, 3, 4, 500)]
    assert client.keys == [4]
    assert client.started == ["com.qq.reader"]
    assert client.stopped == ["com.qq.reader"]


def test_device_controller_tap_feature_uses_locator() -> None:
    client = FakeMaaClient()
    device = MaaDeviceController(client, FakeLocator({"known": (100, 200)}))
    assert device.tap_feature("known") is True
    assert device.tap_feature("missing") is False
    assert client.clicks == [(100, 200)]


def test_observer_builds_observation_from_fake_maa() -> None:
    def recognizer(reco_type: str, params: Mapping[str, Any], shot: Screenshot):
        if reco_type == "OCR":
            return RecoResult(
                "OCR",
                True,
                detail={"all": [{"box": [1, 2, 3, 4], "text": "看小视频领好礼", "score": 0.99}]},
            )
        return RecoResult("TemplateMatch", True, box=(10, 10, 20, 20), score=0.9)

    catalog = FeatureCatalog.from_feature_keys(
        templates={
            "game_exit_dialog": "C:/tmp/exit.png",
            "home_nav_my": "C:/tmp/home.png",
        }
    )
    client = FakeMaaClient(recognizer=recognizer)
    observer = MaaPageObserver(
        client, catalog, foreground_probe=FakeProbe(), target_package="com.qq.reader"
    )

    observation = observer.observe()

    assert "看小视频领好礼" in observation.ocr_texts
    assert observation.templates["game_exit_dialog"] == pytest.approx(0.9)
    assert observation.icons["home_nav_my"] == pytest.approx(0.9)
    assert observation.current_app == "com.qq.reader"
    assert observation.app_installed is True
    assert observation.orientation is Orientation.PORTRAIT
    assert observer.last_screenshot is not None


def test_locator_ocr_returns_box_center() -> None:
    def recognizer(reco_type: str, params: Mapping[str, Any], shot: Screenshot):
        assert reco_type == "OCR"
        assert params["expected"] == "看小视频领好礼"
        return RecoResult("OCR", True, box=(10, 20, 100, 40))

    client = FakeMaaClient(recognizer=recognizer)
    locator = MaaFeatureLocator(client, FeatureCatalog.from_feature_keys())
    assert locator.center("reward_ocr_ad_banner") == (60, 40)


def test_locator_skips_uncalibrated_template() -> None:
    client = FakeMaaClient()
    locator = MaaFeatureLocator(client, FeatureCatalog.from_feature_keys())
    assert locator.center("home_nav_my") is None
    assert client.recognitions == []


def test_doctor_with_fake_client_passes() -> None:
    def factory() -> FakeMaaClient:
        return FakeMaaClient(
            recognizer=lambda reco_type, params, shot: RecoResult(
                "OCR", True, detail={"all": [{"box": [0, 0, 10, 10], "text": "hi", "score": 0.9}]}
            )
        )

    report = run_doctor(default_config(), client_factory=factory)
    assert report.ok
    assert [check.name for check in report.checks] == [
        "构建客户端",
        "连接控制器",
        "截图",
        "OCR",
        "点击",
    ]


def test_doctor_reports_connection_failure() -> None:
    class BrokenClient(FakeMaaClient):
        def connect(self) -> None:
            raise MaaClientError("连不上模拟器")

    report = run_doctor(default_config(), client_factory=lambda: BrokenClient())
    assert not report.ok
    assert any("连不上模拟器" in check.detail for check in report.checks)


def test_parse_foreground_package() -> None:
    assert (
        parse_foreground_package(
            "  mCurrentFocus=Window{abc u0 com.qq.reader/com.qq.reader.MainActivity}"
        )
        == "com.qq.reader"
    )
    assert (
        parse_foreground_package(
            "  mResumedActivity: ActivityRecord{abc u0 com.tencent.mobileqq/.SplashActivity t1}"
        )
        == "com.tencent.mobileqq"
    )
    assert parse_foreground_package("") is None


def test_build_maa_client_requires_runtime_dir() -> None:
    with pytest.raises(MaaClientError, match="maa_runtime_dir"):
        build_maa_client(default_config())


def _maa_config(**machine_overrides: Any):
    machine = {
        "adb_path": "C:\\tools\\adb.exe",
        "adb_address": "127.0.0.1:16384",
        "maa_runtime_dir": "C:\\MaaFramework",
        "maa_resource_dir": "C:\\MaaFramework\\resource",
    }
    machine.update(machine_overrides)
    return loads_config(
        json.dumps(
            {
                "version": 1,
                "machine": machine,
                "captcha": {"solver": "manual"},
                "tasks": {
                    "DailyAdFlow": {"enabled": True, "timeout_seconds": 99},
                    "DailyGameFlow": {"enabled": False},
                },
            }
        )
    )


def test_build_maa_runtime_wires_registry_and_catalog() -> None:
    config = _maa_config()
    runtime = build_maa_runtime(config, connect=False)
    assert runtime.registry.names() == (AD_TASK_NAME,)
    assert runtime.registry.get(AD_TASK_NAME).contract.timeout.seconds == 99
    assert runtime.observer.catalog is runtime.catalog
    assert runtime.device is not None
