"""把 :class:`MaaClient` 适配成 :class:`~qqreader.runtime.device.DeviceController`。"""

from __future__ import annotations

from typing import Optional

from ..runtime.device import DeviceController
from .client import MaaClient
from .locator import FeatureLocator

KEYCODE_BACK = 4


class MaaDeviceController:
    """真实设备控制：点击 / 滑动 / 返回 / 启动 / 停止。"""

    def __init__(
        self,
        client: MaaClient,
        locator: Optional[FeatureLocator] = None,
        *,
        keycode_back: int = KEYCODE_BACK,
    ) -> None:
        self._client = client
        self._locator = locator
        self._keycode_back = keycode_back

    def tap_feature(self, name: str) -> bool:
        if self._locator is None:
            return False
        center = self._locator.center(name)
        if center is None:
            return False
        return bool(self._client.click(center[0], center[1]))

    def tap_point(self, x: int, y: int) -> None:
        self._client.click(int(x), int(y))

    def swipe(
        self, x0: int, y0: int, x1: int, y1: int, duration_ms: int = 300
    ) -> None:
        self._client.swipe(int(x0), int(y0), int(x1), int(y1), int(duration_ms))

    def press_back(self) -> None:
        self._client.click_key(self._keycode_back)

    def launch_app(self, package: str) -> None:
        self._client.start_app(package)

    def stop_app(self, package: str) -> None:
        self._client.stop_app(package)
