"""配置层异常。"""

from __future__ import annotations

from ..errors import QqReaderError


class ConfigError(QqReaderError):
    """配置文件缺失、格式错误或字段非法。

    错误信息必须能指导用户修复（指出字段路径），而不是只抛一个 ``KeyError``。
    """
