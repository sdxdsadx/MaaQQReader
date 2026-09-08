"""配置层：机器差异、任务参数与验证码参数全部外置。

约束（AGENTS.md §4 / QQR-2）：

* 源码不写死盘符、用户名、项目绝对路径；机器差异进本机配置；
* 配置文件统一 UTF-8，支持中文与空格路径；
* 缺少必需配置时给出**清晰**的错误，而不是默默用默认值；
* 真实密钥/账号不写入仓库，示例配置只含占位值。
"""

from .errors import ConfigError
from .loader import (
    ENV_PREFIX,
    build_config,
    default_config,
    load_config,
    loads_config,
    parse_config,
)
from .model import AppConfig, CaptchaConfig, MachineConfig, TaskConfig

__all__ = [
    "ENV_PREFIX",
    "AppConfig",
    "CaptchaConfig",
    "ConfigError",
    "MachineConfig",
    "TaskConfig",
    "build_config",
    "default_config",
    "load_config",
    "loads_config",
    "parse_config",
]
