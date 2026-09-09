"""配置数据模型（纯数据，不负责读文件）。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from .errors import ConfigError

DEFAULT_PACKAGE = "com.qq.reader"
DEFAULT_RESOLUTION: Tuple[int, int] = (720, 1280)


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            f"缺少必需配置 {field_name}（当前值: {value!r}）；"
            "请复制 configs/qqreader.example.json 并填写本机路径"
        )
    return value.strip()


def _optional_text(value: object, field_name: str) -> Optional[str]:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{field_name} 必须是字符串，当前值: {value!r}")
    return value.strip() or None


def _as_path(value: object, field_name: str) -> Path:
    if isinstance(value, Path):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field_name} 必须是非空路径字符串，当前值: {value!r}")
    return Path(value)


def _as_resolution(value: object) -> Tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            width, height = int(value[0]), int(value[1])
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"machine.resolution 必须是两个整数，当前值: {value!r}") from exc
    elif isinstance(value, str) and "x" in value.lower():
        left, _, right = value.lower().partition("x")
        try:
            width, height = int(left), int(right)
        except ValueError as exc:
            raise ConfigError(
                f"machine.resolution 字符串格式应为 720x1280，当前值: {value!r}"
            ) from exc
    else:
        raise ConfigError(
            f"machine.resolution 必须是 [宽, 高] 或 '720x1280'，当前值: {value!r}"
        )
    if width <= 0 or height <= 0:
        raise ConfigError(f"machine.resolution 必须为正整数，当前值: {value!r}")
    return width, height


@dataclass(frozen=True)
class MachineConfig:
    """机器差异：只放本机路径/地址/分辨率，不放业务参数。"""

    adb_path: str
    adb_address: str
    package_name: str = DEFAULT_PACKAGE
    emulator_path: Optional[str] = None
    python_executable: Optional[str] = None
    resolution: Tuple[int, int] = DEFAULT_RESOLUTION
    #: 运行记录与源码分离存放（AGENTS.md §4）。
    screenshot_dir: Path = Path("runtime/screenshots")
    log_dir: Path = Path("runtime/logs")
    record_dir: Path = Path("runtime/records")
    #: MaaFramework 运行时（含 MaaFramework.dll 与各 ControlUnit 依赖）。
    maa_runtime_dir: Optional[Path] = None
    #: Maa 资源包目录（含 OCR 模型与 pipeline；识别必需）。
    maa_resource_dir: Optional[Path] = None
    #: MaaAgentBinary 目录（ADB 控制器需要）。
    maa_agent_dir: Optional[Path] = None
    #: controller="custom" 时使用的静态截图目录（离线自检/集成测试）。
    maa_custom_dir: Optional[Path] = None
    #: "adb"（真机/模拟器）或 "custom"（静态截图，离线）。
    maa_controller: str = "adb"
    #: 截图缩放目标短边（旧工程用 720 保持坐标体系）；None 表示不缩放。
    maa_short_side: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "adb_path", _require_text(self.adb_path, "machine.adb_path"))
        object.__setattr__(
            self, "adb_address", _require_text(self.adb_address, "machine.adb_address")
        )
        object.__setattr__(
            self, "package_name", _require_text(self.package_name, "machine.package_name")
        )
        object.__setattr__(
            self, "emulator_path", _optional_text(self.emulator_path, "machine.emulator_path")
        )
        object.__setattr__(
            self,
            "python_executable",
            _optional_text(self.python_executable, "machine.python_executable"),
        )
        object.__setattr__(self, "resolution", _as_resolution(self.resolution))
        for name in ("screenshot_dir", "log_dir", "record_dir"):
            object.__setattr__(self, name, _as_path(getattr(self, name), f"machine.{name}"))
        for name in ("maa_runtime_dir", "maa_resource_dir", "maa_agent_dir", "maa_custom_dir"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _as_path(value, f"machine.{name}"))
        if self.maa_controller not in ("adb", "custom"):
            raise ConfigError(
                f"machine.maa_controller 必须是 'adb' 或 'custom'，当前: {self.maa_controller!r}"
            )
        if self.maa_short_side is not None and int(self.maa_short_side) <= 0:
            raise ConfigError("machine.maa_short_side 必须 > 0 或 null")

    def resolve_paths(self, base_dir: Path) -> "MachineConfig":
        """把相对目录解析到配置文件所在目录（支持中文与空格路径）。"""
        base = Path(base_dir)

        def _resolve(value: Path) -> Path:
            return value if value.is_absolute() else (base / value)

        optional = {
            name: (_resolve(value) if (value := getattr(self, name)) is not None else None)
            for name in ("maa_runtime_dir", "maa_resource_dir", "maa_agent_dir", "maa_custom_dir")
        }
        return replace(
            self,
            screenshot_dir=_resolve(self.screenshot_dir),
            log_dir=_resolve(self.log_dir),
            record_dir=_resolve(self.record_dir),
            **optional,
        )

    def missing_paths(self) -> Tuple[Path, ...]:
        """严格校验时使用：列出配置里写了但实际不存在的可执行文件/目录。"""
        missing = []
        for raw in (self.adb_path, self.emulator_path, self.python_executable):
            if raw and not Path(raw).exists():
                missing.append(Path(raw))
        return tuple(missing)

    def describe(self) -> str:
        lines = [
            "机器配置:",
            f"  adb_path        = {self.adb_path}",
            f"  adb_address     = {self.adb_address}",
            f"  package_name    = {self.package_name}",
            f"  resolution      = {self.resolution[0]}x{self.resolution[1]}",
        ]
        if self.emulator_path:
            lines.append(f"  emulator_path   = {self.emulator_path}")
        if self.python_executable:
            lines.append(f"  python_executable = {self.python_executable}")
        lines.extend(
            [
                f"  screenshot_dir  = {self.screenshot_dir}",
                f"  log_dir         = {self.log_dir}",
                f"  record_dir      = {self.record_dir}",
                f"  maa_controller  = {self.maa_controller}",
            ]
        )
        for label, value in (
            ("maa_runtime_dir", self.maa_runtime_dir),
            ("maa_resource_dir", self.maa_resource_dir),
            ("maa_agent_dir", self.maa_agent_dir),
            ("maa_custom_dir", self.maa_custom_dir),
        ):
            if value is not None:
                lines.append(f"  {label:<15} = {value}")
        if self.maa_short_side is not None:
            lines.append(f"  maa_short_side  = {self.maa_short_side}")
        return "\n".join(lines)


@dataclass(frozen=True)
class CaptchaConfig:
    """验证码参数：默认人工兜底，自动求解必须显式开启。"""

    solver: str = "manual"
    max_attempts: int = 2
    verify_frames: int = 3
    verify_interval_seconds: float = 1.0
    slide_roi: Optional[Tuple[int, int, int, int]] = None

    _SOLVERS = ("manual", "ddddocr", "slide", "auto")

    def __post_init__(self) -> None:
        if self.solver not in self._SOLVERS:
            raise ConfigError(
                f"captcha.solver 必须是 {list(self._SOLVERS)} 之一，当前值: {self.solver!r}"
            )
        if self.max_attempts < 1:
            raise ConfigError("captcha.max_attempts 必须 >= 1")
        if self.verify_frames < 1:
            raise ConfigError("captcha.verify_frames 必须 >= 1")
        if self.verify_interval_seconds <= 0:
            raise ConfigError("captcha.verify_interval_seconds 必须 > 0")
        if self.slide_roi is not None:
            if len(self.slide_roi) != 4 or any(int(v) < 0 for v in self.slide_roi):
                raise ConfigError(
                    f"captcha.slide_roi 必须是 [x, y, w, h] 四个非负整数，当前值: {self.slide_roi!r}"
                )
            object.__setattr__(self, "slide_roi", tuple(int(v) for v in self.slide_roi))

    def describe(self) -> str:
        roi = f"{self.slide_roi}" if self.slide_roi else "(未配置)"
        return (
            f"验证码: solver={self.solver} max_attempts={self.max_attempts} "
            f"verify={self.verify_frames}帧/{self.verify_interval_seconds}s slide_roi={roi}"
        )


@dataclass(frozen=True)
class TaskConfig:
    """单个任务的工程参数（成功/失败条件仍在任务契约里，不在这里）。"""

    name: str
    enabled: bool = True
    timeout_seconds: Optional[float] = None
    retry: int = 3
    feature_overrides: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ConfigError("tasks 的每个条目必须有非空 name")
        object.__setattr__(self, "name", self.name.strip())
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ConfigError(f"tasks.{self.name}.timeout_seconds 必须 > 0")
        if self.retry < 1:
            raise ConfigError(f"tasks.{self.name}.retry 必须 >= 1")
        if not isinstance(self.feature_overrides, Mapping):
            raise ConfigError(f"tasks.{self.name}.feature_overrides 必须是对象")

    def describe(self) -> str:
        timeout = f"{self.timeout_seconds:g}s" if self.timeout_seconds else "(用契约默认)"
        return (
            f"任务 {self.name}: enabled={self.enabled} timeout={timeout} "
            f"retry={self.retry} feature_overrides={len(self.feature_overrides)} 项"
        )


@dataclass(frozen=True)
class AppConfig:
    """一份完整配置。"""

    machine: MachineConfig
    tasks: Mapping[str, TaskConfig] = field(default_factory=dict)
    captcha: CaptchaConfig = field(default_factory=CaptchaConfig)
    version: int = 1
    #: 配置文件的绝对路径（便于日志与排障）。
    source: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ConfigError("version 必须 >= 1")
        normalized: Dict[str, TaskConfig] = {}
        for name, task in self.tasks.items():
            if not isinstance(task, TaskConfig):
                raise ConfigError(f"tasks.{name} 必须是 TaskConfig")
            if task.name != name:
                raise ConfigError(f"tasks 键 {name!r} 与 name={task.name!r} 不一致")
            normalized[name] = task
        object.__setattr__(self, "tasks", normalized)

    def task(self, name: str) -> TaskConfig:
        try:
            return self.tasks[name]
        except KeyError as exc:
            raise ConfigError(
                f"配置中没有任务 {name!r}；已配置: {sorted(self.tasks)}"
            ) from exc

    def enabled_tasks(self) -> Tuple[TaskConfig, ...]:
        return tuple(t for t in self.tasks.values() if t.enabled)

    def describe(self) -> str:
        lines = [f"QQReader 配置 (version={self.version})", self.machine.describe(), self.captcha.describe()]
        if self.tasks:
            lines.append("任务:")
            lines.extend("  " + task.describe() for task in self.tasks.values())
        else:
            lines.append("任务: (未配置)")
        if self.source is not None:
            lines.append(f"来源: {self.source}")
        return "\n".join(lines)
