"""配置读取与校验。

支持 JSON（标准库）与 YAML（可选，需 PyYAML）；文件必须 UTF-8。
机器差异可用环境变量覆盖，便于不同机器/CI 不改配置文件：

    QQREADER_ADB_PATH / QQREADER_ADB_ADDRESS / QQREADER_PACKAGE_NAME
    QQREADER_EMULATOR_PATH / QQREADER_PYTHON_EXECUTABLE / QQREADER_RESOLUTION
    QQREADER_SCREENSHOT_DIR / QQREADER_LOG_DIR / QQREADER_RECORD_DIR
    QQREADER_CAPTCHA_SOLVER / QQREADER_CAPTCHA_MAX_ATTEMPTS ...
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional

from .errors import ConfigError
from .model import AppConfig, CaptchaConfig, MachineConfig, TaskConfig

ENV_PREFIX = "QQREADER_"

_ALLOWED_TOP = {"version", "machine", "captcha", "tasks"}
_ALLOWED_MACHINE = {
    "adb_path",
    "adb_address",
    "package_name",
    "emulator_path",
    "python_executable",
    "resolution",
    "screenshot_dir",
    "log_dir",
    "record_dir",
    "maa_runtime_dir",
    "maa_resource_dir",
    "maa_agent_dir",
    "maa_custom_dir",
    "maa_controller",
    "maa_short_side",
}
_ALLOWED_CAPTCHA = {
    "solver",
    "max_attempts",
    "verify_frames",
    "verify_interval_seconds",
    "slide_roi",
}
_ALLOWED_TASK = {"name", "enabled", "timeout_seconds", "retry", "feature_overrides"}

_ENV_MACHINE = {
    "ADB_PATH": "adb_path",
    "ADB_ADDRESS": "adb_address",
    "PACKAGE_NAME": "package_name",
    "EMULATOR_PATH": "emulator_path",
    "PYTHON_EXECUTABLE": "python_executable",
    "RESOLUTION": "resolution",
    "SCREENSHOT_DIR": "screenshot_dir",
    "LOG_DIR": "log_dir",
    "RECORD_DIR": "record_dir",
    "MAA_RUNTIME_DIR": "maa_runtime_dir",
    "MAA_RESOURCE_DIR": "maa_resource_dir",
    "MAA_AGENT_DIR": "maa_agent_dir",
    "MAA_CUSTOM_DIR": "maa_custom_dir",
    "MAA_CONTROLLER": "maa_controller",
    "MAA_SHORT_SIDE": "maa_short_side",
}
_ENV_CAPTCHA = {
    "CAPTCHA_SOLVER": "solver",
    "CAPTCHA_MAX_ATTEMPTS": "max_attempts",
    "CAPTCHA_VERIFY_FRAMES": "verify_frames",
    "CAPTCHA_VERIFY_INTERVAL": "verify_interval_seconds",
}
_INT_ENV = {"max_attempts", "verify_frames", "maa_short_side"}
_FLOAT_ENV = {"verify_interval_seconds"}


def parse_config(text: str, suffix: str, *, source: str = "<memory>") -> Any:
    """把配置文本解析成 Python 对象；格式错误时给出可定位的错误。"""
    normalized = suffix.lower()
    if normalized == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{source}: JSON 解析失败: {exc}") from exc
    if normalized in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - 取决于是否安装 PyYAML
            raise ConfigError(
                f"{source}: 读取 YAML 需要 PyYAML（pip install PyYAML）"
            ) from exc
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"{source}: YAML 解析失败: {exc}") from exc
    raise ConfigError(
        f"{source}: 不支持的配置格式 {suffix!r}（仅支持 .json / .yaml / .yml）"
    )


def _reject_unknown(data: Mapping[str, Any], allowed: set, where: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(f"{where} 含未知字段 {unknown}；允许字段: {sorted(allowed)}")


def _section(data: Mapping[str, Any], key: str, *, required: bool) -> dict:
    raw = data.get(key)
    if raw is None:
        if required:
            raise ConfigError(f"缺少必需配置节 {key!r}")
        return {}
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{key} 必须是对象，当前: {type(raw).__name__}")
    return dict(raw)


def _apply_env(section: dict, mapping: Mapping[str, str], env: Mapping[str, str]) -> dict:
    result = dict(section)
    for env_key, field in mapping.items():
        full = ENV_PREFIX + env_key
        value = env.get(full)
        if value is None or value == "":
            continue
        if field in _INT_ENV:
            try:
                value = int(value)  # type: ignore[assignment]
            except ValueError as exc:
                raise ConfigError(f"环境变量 {full} 必须是整数，当前: {value!r}") from exc
        elif field in _FLOAT_ENV:
            try:
                value = float(value)  # type: ignore[assignment]
            except ValueError as exc:
                raise ConfigError(f"环境变量 {full} 必须是数字，当前: {value!r}") from exc
        result[field] = value
    return result


_REQUIRED_MACHINE = ("adb_path", "adb_address")


def _construct(factory, data: Mapping[str, Any], where: str):
    """把 dataclass 构造期的 TypeError 转成可定位的 ConfigError。"""
    try:
        return factory(**data)
    except ConfigError:
        raise
    except TypeError as exc:
        raise ConfigError(f"{where} 配置有误: {exc}") from exc


def build_config(
    data: Mapping[str, Any],
    *,
    base_dir: Path,
    env: Optional[Mapping[str, str]] = None,
    source: Optional[Path] = None,
) -> AppConfig:
    """从已解析的对象构造 :class:`AppConfig`。"""
    if not isinstance(data, Mapping):
        raise ConfigError(f"配置根节点必须是对象，当前: {type(data).__name__}")
    _reject_unknown(data, _ALLOWED_TOP, "根配置")

    version = data.get("version", 1)
    if not isinstance(version, int) or version < 1:
        raise ConfigError(f"version 必须是 >= 1 的整数，当前: {version!r}")

    environment = dict(os.environ) if env is None else dict(env)

    machine_data = _apply_env(
        _section(data, "machine", required=True), _ENV_MACHINE, environment
    )
    _reject_unknown(machine_data, _ALLOWED_MACHINE, "machine")
    missing = [f"machine.{key}" for key in _REQUIRED_MACHINE if not machine_data.get(key)]
    if missing:
        raise ConfigError(
            f"缺少必需配置 {', '.join(missing)}；"
            "请复制 configs/qqreader.example.json 并填写本机路径"
        )
    machine = _construct(MachineConfig, machine_data, "machine").resolve_paths(
        Path(base_dir)
    )

    captcha_data = _apply_env(
        _section(data, "captcha", required=False), _ENV_CAPTCHA, environment
    )
    _reject_unknown(captcha_data, _ALLOWED_CAPTCHA, "captcha")
    captcha = _construct(CaptchaConfig, captcha_data, "captcha")

    raw_tasks = data.get("tasks", {})
    if not isinstance(raw_tasks, Mapping):
        raise ConfigError(f"tasks 必须是对象，当前: {type(raw_tasks).__name__}")
    tasks = {}
    for name, raw in raw_tasks.items():
        if not isinstance(raw, Mapping):
            raise ConfigError(f"tasks.{name} 必须是对象，当前: {type(raw).__name__}")
        _reject_unknown(raw, _ALLOWED_TASK, f"tasks.{name}")
        task_data = dict(raw)
        if "name" in task_data and task_data["name"] != name:
            raise ConfigError(
                f"tasks.{name}.name 与键不一致: {task_data['name']!r} != {name!r}"
            )
        task_data["name"] = name
        tasks[name] = _construct(TaskConfig, task_data, f"tasks.{name}")

    return AppConfig(
        machine=machine,
        tasks=tasks,
        captcha=captcha,
        version=version,
        source=source,
    )


def load_config(
    path: Path,
    *,
    base_dir: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
) -> AppConfig:
    """读取配置文件（UTF-8，支持中文/空格路径）。"""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"配置文件不存在: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{path}: 配置文件不是 UTF-8 编码: {exc}") from exc
    data = parse_config(text, path.suffix, source=str(path))
    return build_config(
        data,
        base_dir=base_dir or path.parent,
        env=env,
        source=path.resolve(),
    )


def loads_config(
    text: str,
    *,
    suffix: str = ".json",
    base_dir: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    source: str = "<memory>",
) -> AppConfig:
    """从内存文本读取配置（测试/导入用）。"""
    data = parse_config(text, suffix, source=source)
    return build_config(
        data,
        base_dir=base_dir or Path.cwd(),
        env=env,
        source=None,
    )


def default_config() -> AppConfig:
    """占位默认配置：只用于启动自检，**不含**真实机器路径/账号。"""
    return AppConfig(
        machine=MachineConfig(
            adb_path="C:\\path\\to\\adb.exe",
            adb_address="127.0.0.1:16384",
        ),
        tasks={
            "DailyAdFlow": TaskConfig(
                name="DailyAdFlow", timeout_seconds=45 * 60, retry=3
            ),
            "DailyGameFlow": TaskConfig(
                name="DailyGameFlow", timeout_seconds=30 * 60, retry=3
            ),
        },
    )
