"""任务目录、分级设置与串行计划（纯逻辑，不依赖 Tkinter）。

任务列表按旧 GUI 的 `assets/interface.json` 顺序迁移；未接入新流程的任务会保留
在树中，但运行时会由 ``scripts/run_task.py`` 明确输出「未接入」。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class TaskSettingField:
    """一个任务参数的 UI 描述。"""

    key: str
    label: str
    kind: str = "float"  # float / int / bool
    default: Any = 0
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: float = 1
    unit: str = ""
    help: str = ""

    def normalize(self, raw: Any) -> Any:
        if self.kind == "bool":
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, str):
                return raw.strip().lower() in {"1", "true", "yes", "on"}
            return bool(raw)
        if self.kind == "int":
            value = int(float(raw))
        else:
            value = float(raw)
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f"{self.label} 不能小于 {self.minimum:g}")
        if self.maximum is not None and value > self.maximum:
            raise ValueError(f"{self.label} 不能大于 {self.maximum:g}")
        return value


@dataclass(frozen=True)
class TaskSpec:
    """一个可执行任务的分级描述。"""

    key: str
    name: str
    group: str
    description: str
    legacy_name: str = ""
    entry: str = ""
    implemented: bool = True
    default_enabled: bool = False
    fields: Tuple[TaskSettingField, ...] = ()

    @property
    def display_name(self) -> str:
        base = self.legacy_name or self.name
        if not self.implemented:
            return f"{base}（旧流程）"
        return base

    def field(self, key: str) -> TaskSettingField:
        for item in self.fields:
            if item.key == key:
                return item
        raise KeyError(key)


@dataclass
class TaskSettings:
    """单个任务的启用状态与参数值。"""

    enabled: bool
    values: Dict[str, Any] = field(default_factory=dict)

    def value(self, spec: TaskSpec, key: str, default: Any = None) -> Any:
        if key in self.values:
            return self.values[key]
        try:
            return spec.field(key).default
        except KeyError:
            return default

    def normalized(self, spec: TaskSpec) -> "TaskSettings":
        values: Dict[str, Any] = {}
        for item in spec.fields:
            values[item.key] = item.normalize(
                self.values.get(item.key, item.default)
            )
        return TaskSettings(enabled=bool(self.enabled), values=values)

    def to_dict(self) -> Dict[str, Any]:
        return {"enabled": bool(self.enabled), "values": dict(self.values)}

    @classmethod
    def from_dict(
        cls, spec: TaskSpec, raw: Optional[Mapping[str, Any]]
    ) -> "TaskSettings":
        data = dict(raw or {})
        values = dict(data.get("values") or {})
        return cls(
            enabled=bool(data.get("enabled", spec.default_enabled)),
            values=values,
        )


@dataclass(frozen=True)
class TaskRunPlan:
    spec: TaskSpec
    settings: TaskSettings
    repeat_index: int = 1
    repeat_total: int = 1


def _count_field(default: int = 1, maximum: int = 99) -> TaskSettingField:
    return TaskSettingField(
        key="count",
        label="重复次数",
        kind="int",
        default=default,
        minimum=1,
        maximum=maximum,
        step=1,
    )


def _minutes_field(default: float = 1) -> TaskSettingField:
    return TaskSettingField(
        key="minutes",
        label="每次分钟",
        kind="float",
        default=default,
        minimum=0.1,
        maximum=240.0,
        step=1.0,
        unit="分钟",
    )


def _timeout_field(default: float = 30) -> TaskSettingField:
    return TaskSettingField(
        key="timeout_minutes",
        label="任务超时",
        kind="float",
        default=default,
        minimum=0.1,
        maximum=240.0,
        step=1.0,
        unit="分钟",
    )


def _max_steps_field(default: int = 2000) -> TaskSettingField:
    return TaskSettingField(
        key="max_steps",
        label="最大步数",
        kind="int",
        default=default,
        minimum=1,
        maximum=20000,
        step=100,
    )


DEFAULT_TASK_CATALOG: Tuple[TaskSpec, ...] = (
    TaskSpec(
        key="LaunchQQReader",
        name="启动 QQ 阅读",
        group="启动与检查",
        legacy_name="00 启动 QQ 阅读并关闭开屏弹窗",
        entry="LaunchQQReader",
        description="启动 QQ 阅读并处理已知开屏弹窗。",
        default_enabled=False,
        fields=(),
    ),
    TaskSpec(
        key="SmokeTest",
        name="页面识别检查",
        group="启动与检查",
        legacy_name="00 页面识别检查",
        entry="SmokeTest",
        description="连接 MAA、截图并输出当前页面状态/OCR，用于检查识别链路。",
        default_enabled=False,
        fields=(),
    ),
    TaskSpec(
        key="DailyReadingFlow",
        name="每日自动阅读",
        group="阅读任务",
        legacy_name="01 每日自动阅读（默认2次×35分钟）",
        entry="DailyReadingFlow",
        implemented=False,
        default_enabled=False,
        description="调用旧 QQ 阅读 pipeline 的自动阅读流程。",
        fields=(_count_field(2), _minutes_field(35), _timeout_field(240)),
    ),
    TaskSpec(
        key="DailyAudiobookFlow",
        name="每日听书",
        group="听书任务",
        legacy_name="02 每日听书（默认35分钟，结束后暂停）",
        entry="DailyAudiobookFlow",
        implemented=False,
        default_enabled=False,
        description="调用旧 QQ 阅读 pipeline 的听书流程。",
        fields=(_count_field(1), _minutes_field(35), _timeout_field(240)),
    ),
    TaskSpec(
        key="DailyGameFlow",
        name="每日游戏",
        group="游戏任务",
        legacy_name="03 每日游戏（默认25分钟）",
        entry="DailyGameFlow",
        default_enabled=True,
        description=(
            "奖励页 → 去玩游戏 → 游戏大厅下划 → 在线玩 → 游戏中心 → "
            "登录/协议 → 领币计时 → 退出 → 返回奖励页"
        ),
        fields=(
            _count_field(1),
            TaskSettingField(
                key="duration_minutes",
                label="挂机分钟",
                kind="float",
                default=22.0,
                minimum=0.02,
                maximum=180.0,
                step=1.0,
                unit="分钟",
            ),
            _timeout_field(30),
            _max_steps_field(),
        ),
    ),
    TaskSpec(
        key="DailyAdFlow",
        name="每日广告完整流程",
        group="奖励任务",
        legacy_name="04 每日广告完整流程（自动至12/12）",
        entry="DailyAdFlow",
        default_enabled=True,
        description="奖励页视频广告：主页 → 奖励页 → 观看广告 → 返回奖励页 → 判断次数/验证码。",
        fields=(_count_field(1, maximum=1), _timeout_field(45), _max_steps_field()),
    ),
    TaskSpec(
        key="DailyExternalAppFlow",
        name="外部应用每日流程",
        group="外部应用",
        legacy_name="05 外部应用每日流程（大众点评+百度地图）",
        entry="DailyExternalAppFlow",
        implemented=False,
        default_enabled=False,
        description="调用旧 QQ 阅读 pipeline 的外部应用跳转流程。",
        fields=(_count_field(1, maximum=1), _timeout_field(30)),
    ),
    TaskSpec(
        key="DailyLevelAdFlow",
        name="等级页广告每日流程",
        group="等级广告",
        legacy_name="06 等级页广告每日流程（赠币+积分）",
        entry="DailyLevelAdFlow",
        implemented=False,
        default_enabled=False,
        description="调用旧 QQ 阅读 pipeline 的等级页广告流程。",
        fields=(_count_field(1, maximum=1), _timeout_field(30)),
    ),
    TaskSpec(
        key="ClaimOneReward",
        name="领取全部已完成奖励",
        group="奖励领取",
        legacy_name="07 领取全部已完成奖励",
        entry="ClaimOneReward",
        implemented=False,
        default_enabled=False,
        description="调用旧 QQ 阅读 pipeline 的奖励领取流程。",
        fields=(_count_field(1, maximum=1), _timeout_field(10)),
    ),
)


def default_settings(
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG,
) -> Dict[str, TaskSettings]:
    return {
        spec.key: TaskSettings(
            enabled=spec.default_enabled,
            values={item.key: item.default for item in spec.fields},
        )
        for spec in catalog
    }


def ordered_catalog(
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG,
    order: Optional[Sequence[str]] = None,
) -> List[TaskSpec]:
    """按保存的顺序返回任务；未保存的任务追加在目录顺序后面。"""
    if not order:
        return list(catalog)
    by_key = {spec.key: spec for spec in catalog}
    result: List[TaskSpec] = []
    seen = set()
    for key in order:
        spec = by_key.get(key)
        if spec is not None and key not in seen:
            result.append(spec)
            seen.add(key)
    for spec in catalog:
        if spec.key not in seen:
            result.append(spec)
    return result


def load_task_settings(
    path: Path,
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG,
) -> Dict[str, TaskSettings]:
    defaults = default_settings(catalog)
    if not path.is_file():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults
    tasks = raw.get("tasks") if isinstance(raw, dict) else None
    if not isinstance(tasks, dict):
        return defaults
    for spec in catalog:
        data = tasks.get(spec.key)
        if isinstance(data, dict):
            defaults[spec.key] = TaskSettings.from_dict(spec, data)
    return defaults


def load_task_order(
    path: Path,
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG,
) -> List[TaskSpec]:
    if not path.is_file():
        return list(catalog)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return list(catalog)
    order = raw.get("order") if isinstance(raw, dict) else None
    if not isinstance(order, list):
        return list(catalog)
    return ordered_catalog(catalog, [str(item) for item in order])


def save_task_settings(
    path: Path,
    settings: Mapping[str, TaskSettings],
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG,
    *,
    order: Optional[Sequence[str]] = None,
) -> None:
    payload: Dict[str, Any] = {
        "tasks": {
            spec.key: settings.get(
                spec.key, TaskSettings(enabled=spec.default_enabled)
            ).to_dict()
            for spec in catalog
        }
    }
    if order is not None:
        payload["order"] = [str(item) for item in order]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_serial_plan(
    settings: Mapping[str, TaskSettings],
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG,
    *,
    order: Optional[Sequence[str]] = None,
) -> List[TaskRunPlan]:
    """按顺序展开已启用任务；`count` 次任务展开为多个串行步骤。"""
    plan: List[TaskRunPlan] = []
    for spec in ordered_catalog(catalog, order):
        item = settings.get(spec.key)
        if item is None or not item.enabled:
            continue
        normalized = item.normalized(spec)
        count = int(normalized.value(spec, "count", 1) or 1)
        count = max(1, count)
        for index in range(count):
            plan.append(
                TaskRunPlan(
                    spec=spec,
                    settings=normalized,
                    repeat_index=index + 1,
                    repeat_total=count,
                )
            )
    return plan


def describe_catalog(
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG,
) -> str:
    lines: List[str] = []
    groups: Dict[str, List[TaskSpec]] = {}
    for spec in catalog:
        groups.setdefault(spec.group, []).append(spec)
    for group, specs in groups.items():
        lines.append(f"[{group}]")
        for spec in specs:
            suffix = "" if spec.implemented else "（旧流程）"
            lines.append(f"  - {spec.display_name}{suffix} ({spec.key})")
    return "\n".join(lines)
