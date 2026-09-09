"""装配 MaaFramework 运行时：客户端 + 特征目录 + 观测器 + 设备 + 任务注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from ..captcha.guard import CaptchaGuard
from ..config import AppConfig
from ..page.feature_keys import DEFAULT_FEATURE_KEYS, FeatureKeys
from ..runner.registry import TaskRegistry
from ..tasks.defaults import build_default_registry
from .catalog import FeatureCatalog
from .client import MaaClient, MaaClientError
from .ctypes_client import CtypesMaaClient, CtypesMaaConfig
from .device import MaaDeviceController
from .locator import MaaFeatureLocator
from .observer import MaaPageObserver
from .probes import DeviceProbe, SubprocessShellRunner


def build_ctypes_config(
    config: AppConfig,
    *,
    controller: Optional[str] = None,
    custom_images: Sequence[bytes] = (),
    custom_dir: Optional[Path] = None,
) -> CtypesMaaConfig:
    """把 :class:`AppConfig` 的机器差异映射到 Maa 客户端配置。"""
    machine = config.machine
    if machine.maa_runtime_dir is None:
        raise MaaClientError(
            "缺少 machine.maa_runtime_dir（MaaFramework.dll 所在目录）；"
            "请复制 configs/qqreader.example.json 并填写"
        )
    return CtypesMaaConfig(
        runtime_dir=machine.maa_runtime_dir,
        resource_dir=machine.maa_resource_dir,
        controller=controller or machine.maa_controller,
        adb_path=machine.adb_path,
        adb_address=machine.adb_address,
        agent_dir=machine.maa_agent_dir,
        custom_images=tuple(custom_images),
        custom_dir=custom_dir or machine.maa_custom_dir,
        short_side=machine.maa_short_side,
        log_dir=machine.log_dir,
    )


def build_maa_client(
    config: AppConfig,
    *,
    clock: Any = None,
    controller: Optional[str] = None,
    custom_images: Sequence[bytes] = (),
    custom_dir: Optional[Path] = None,
) -> CtypesMaaClient:
    return CtypesMaaClient(
        build_ctypes_config(
            config,
            controller=controller,
            custom_images=custom_images,
            custom_dir=custom_dir,
        ),
        clock=clock,
    )


@dataclass
class MaaRuntime:
    """一套可运行的 MaaFramework 适配。"""

    config: AppConfig
    client: MaaClient
    catalog: FeatureCatalog
    observer: MaaPageObserver
    locator: MaaFeatureLocator
    device: MaaDeviceController
    registry: TaskRegistry

    def connect(self) -> "MaaRuntime":
        self.client.connect()
        return self

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "MaaRuntime":
        return self.connect()

    def __exit__(self, *exc: object) -> None:
        self.close()


def build_maa_runtime(
    config: AppConfig,
    *,
    clock: Any = None,
    keys: FeatureKeys = DEFAULT_FEATURE_KEYS,
    captcha_guard: Optional[CaptchaGuard] = None,
    controller: Optional[str] = None,
    custom_images: Sequence[bytes] = (),
    custom_dir: Optional[Path] = None,
    foreground_probe: Any = None,
    structure_probe: Any = None,
    connect: bool = False,
) -> MaaRuntime:
    """装配运行时；``connect=True`` 时立即连接（失败会抛 :class:`MaaClientError`）。"""
    client = build_maa_client(
        config,
        clock=clock,
        controller=controller,
        custom_images=custom_images,
        custom_dir=custom_dir,
    )
    catalog = FeatureCatalog.from_feature_keys(
        keys,
        # QQR-20：只在下半屏找「在线玩」，避开游戏中心顶部不可点击的 tab。
        rois={"game_ocr_online_play": (0, 800, 720, 1280)},
    )
    if foreground_probe is None and config.machine.adb_path:
        shell = SubprocessShellRunner(config.machine.adb_path, config.machine.adb_address)
        foreground_probe = DeviceProbe(shell)
    observer = MaaPageObserver(
        client,
        catalog,
        foreground_probe=foreground_probe,
        structure_probe=structure_probe,
        target_package=config.machine.package_name,
        clock=clock,
    )
    locator = MaaFeatureLocator(client, catalog, observer=observer)
    device = MaaDeviceController(client, locator)
    registry = build_default_registry(
        observer,
        device,
        keys=keys,
        captcha_guard=captcha_guard,
        config=config,
    )
    runtime = MaaRuntime(
        config=config,
        client=client,
        catalog=catalog,
        observer=observer,
        locator=locator,
        device=device,
        registry=registry,
    )
    if connect:
        runtime.connect()
    return runtime
