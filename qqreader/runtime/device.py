"""设备控制协议。

真实实现由 MaaFramework 适配器提供（后续任务接入阶段）；核心与测试只依赖
这个协议，因此可以完全脱离真机验证状态机与恢复逻辑。
"""

from __future__ import annotations

from typing import Protocol


class DeviceController(Protocol):
    """最小设备控制面。"""

    def tap_feature(self, name: str) -> bool:
        """点击名为 ``name`` 的特征；返回是否成功定位并点击。"""

    def tap_point(self, x: int, y: int) -> None:
        """点击绝对坐标。"""

    def swipe(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        duration_ms: int = 300,
    ) -> None:
        """滑动。"""

    def press_back(self) -> None:
        """按返回键。"""

    def launch_app(self, package: str) -> None:
        """启动应用。"""

    def stop_app(self, package: str) -> None:
        """停止应用。"""
