"""任务目录、分级设置与串行计划（纯逻辑，不依赖 Tkinter）。"""

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
    fields: Tuple[TaskSettingField, ...] = ()
    default_enabled: bool = False
    runnable: bool = True

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

    def value(self, spec: TaskSpec, key: str) -> Any:
        if key in self.values:
            return self.values[key]
        return spec.field(key).default

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


DEFAULT_TASK_CATALOG: Tuple[TaskSpec, ...] = (
    TaskSpec(
        key="DailyGameFlow",
        name="游戏挂机",
        group="日常任务",
        description=(
            "奖励页 → 去玩游戏 → 游戏大厅下划 → 在线玩 → 游戏中心 → "
            "登录/协议 → 领币计时 → 退出 → 返回奖励页"
        ),
        default_enabled=True,
        fields=(
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
            TaskSettingField(
                key="timeout_minutes",
                label="任务超时",
                kind="float",
                default=30.0,
                minimum=0.1,
                maximum=240.0,
                step=1.0,
                unit="分钟",
            ),
            TaskSettingField(
                key="max_steps",
                label="最大步数",
                kind="int",
                default=2000,
                minimum=1,
                maximum=20000,
                step=100,
            ),
        ),
    ),
    TaskSpec(
        key="DailyAdFlow",
        name="奖励页广告",
        group="日常任务",
        description="奖励页视频广告：主页 → 奖励页 → 观看广告 → 返回奖励页 → 判断次数/验证码",
        default_enabled=False,
        fields=(
            TaskSettingField(
                key="timeout_minutes",
                label="任务超时",
                kind="float",
                default=45.0,
                minimum=0.1,
                maximum=240.0,
                step=1.0,
                unit="分钟",
            ),
            TaskSettingField(
                key="max_steps",
                label="最大步数",
                kind="int",
                default=2000,
                minimum=1,
                maximum=20000,
                step=100,
            ),
        ),
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


def load_task_settings(
    path: Path,
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG,
) -> Dict[str, TaskSettings]:
    """读取 runtime/gui_tasks.json；不存在或损坏时返回默认值。"""
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


def save_task_settings(
    path: Path,
    settings: Mapping[str, TaskSettings],
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG,
) -> None:
    payload = {
        "tasks": {
            spec.key: settings.get(
                spec.key, TaskSettings(enabled=spec.default_enabled)
            ).to_dict()
            for spec in catalog
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_serial_plan(
    settings: Mapping[str, TaskSettings],
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG,
) -> List[TaskRunPlan]:
    """按目录顺序返回已启用且可运行的任务。"""
    plan: List[TaskRunPlan] = []
    for spec in catalog:
        if not spec.runnable:
            continue
        item = settings.get(spec.key)
        if item is None or not item.enabled:
            continue
        plan.append(TaskRunPlan(spec=spec, settings=item.normalized(spec)))
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
            suffix = "" if spec.runnable else "（未接入）"
            lines.append(f"  - {spec.name} ({spec.key}){suffix}")
    return "\n".join(lines)
