"""MaaFramework 适配层：真实观测 / 点击 / 识别 / 任务装配。

核心（``page`` / ``contract`` / ``recovery`` / ``captcha`` / ``runner``）不依赖
MaaFramework；本层把 Maa 能力注入核心协议，因此可以：

* 真机：``controller="adb"`` 连接模拟器/真机；
* 离线：``controller="custom"`` 用 Python 回调提供静态截图，配合真实
  ``MaaFramework.dll`` 跑通截图 / OCR / 点击（用于集成测试与 ``doctor``）。
"""

from .catalog import FeatureAsset, FeatureCatalog
from .client import MaaClient, MaaClientError, RecoResult, Screenshot
from .ctypes_client import CtypesMaaClient, CtypesMaaConfig
from .device import MaaDeviceController
from .doctor import DoctorCheck, DoctorReport, run_doctor
from .factory import MaaRuntime, build_ctypes_config, build_maa_client, build_maa_runtime
from .locator import FeatureLocator, MaaFeatureLocator
from .observer import MaaPageObserver
from .probes import (
    DeviceProbe,
    ForegroundAppProbe,
    PackageProbe,
    SubprocessShellRunner,
    parse_foreground_package,
)

__all__ = [
    "CtypesMaaClient",
    "CtypesMaaConfig",
    "DeviceProbe",
    "DoctorCheck",
    "DoctorReport",
    "FeatureAsset",
    "FeatureCatalog",
    "FeatureLocator",
    "ForegroundAppProbe",
    "MaaClient",
    "MaaClientError",
    "MaaDeviceController",
    "MaaFeatureLocator",
    "MaaPageObserver",
    "MaaRuntime",
    "PackageProbe",
    "RecoResult",
    "Screenshot",
    "SubprocessShellRunner",
    "build_ctypes_config",
    "build_maa_client",
    "build_maa_runtime",
    "parse_foreground_package",
    "run_doctor",
]
