"""由任务目录生成 MFAAvalonia 的 ``interface.json`` 与 pipeline。

每个任务对应一个 pipeline 节点 ``QQR_<key>``：``Custom`` 动作 ``QQReaderRunTask``，
``custom_action_param`` 为 ``{"task": key, **字段默认值}``（不含 ``count``，
重复次数交给 MFA 的 ``repeatable`` / ``repeat_count``）。

协议要点（PI V2 文档 3.3 与 MFAAvalonia v2.16.2 源码）：

- MFA 把各选项生成的 ``pipeline_override`` 按顺序整体交给 MaaFramework；同名节点
  只合并顶层键（「资源覆盖」：顶层键直接替换，内部不合并）。多个选项都写同一节点的
  ``custom_action_param`` 会互相覆盖，所以每个任务只生成**一个** ``input`` 选项，
  内含该任务全部参数，并把 ``task`` 一起写进覆盖。
- ``inputs[].pipeline_type`` 只允许 ``string`` / ``int`` / ``bool``，没有 ``double``；
  小数字段用 ``string``，由 Agent 侧 ``TaskSettingField.normalize`` 转成浮点数。
  布尔字段用 ``bool`` 输入（``true`` / ``false``），不用 switch（switch 的覆盖同样会
  整体替换 ``custom_action_param``）。
- ``preset``（PI v2.3.0）的任务项只有 ``name`` / ``enabled`` / ``option``，不能设置
  重复次数。

本模块不导入 ``maa``。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ..gui.task_catalog import (
    DEFAULT_TASK_CATALOG,
    FORMAL_PRESET_KEYS,
    TRIAL_PRESET_KEYS,
    TaskSettingField,
    TaskSpec,
)
from .agent_action import ACTION_NAME

TITLE = "QQ阅读每日任务"
NUMBER_VERIFY = r"^\d+(\.\d+)?$"
INT_VERIFY = r"^\d+$"
BOOL_VERIFY = r"^(true|false)$"
FORMAL_PRESET_NAME = "正式每日"
TRIAL_PRESET_NAME = "1 分钟试跑"
_COUNT_KEY = "count"
_TRIAL_MINUTE_KEYS = frozenset({"minutes", "duration_minutes"})
_PIPELINE_TYPES = {
    "float": "string",
    "int": "int",
    "bool": "bool",
    "text": "string",
    "file": "string",
}


def entry_name(key: str) -> str:
    return f"QQR_{key}"


def option_name(key: str) -> str:
    """每个任务唯一的 ``input`` 选项名。"""
    return f"{key}.settings"


def read_project_version(pyproject: Path) -> str:
    """从 ``pyproject.toml`` 的 ``[project]`` 段读取 ``version``（3.10 无 tomllib）。"""
    text = Path(pyproject).read_text(encoding="utf-8")
    section = re.search(r"^\[project\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    if section is None:
        raise ValueError("pyproject.toml 缺少 [project] 段")
    match = re.search(r'^version\s*=\s*"([^"]+)"', section.group(1), re.M)
    if match is None:
        raise ValueError("pyproject.toml 的 [project] 段缺少 version")
    return match.group(1)


def _settable_fields(spec: TaskSpec) -> List[TaskSettingField]:
    return [item for item in spec.fields if item.key != _COUNT_KEY]


def _count_field(spec: TaskSpec) -> Optional[TaskSettingField]:
    return next((item for item in spec.fields if item.key == _COUNT_KEY), None)


def format_value(item: TaskSettingField, value: Any) -> str:
    """把字段取值写成 MFA 输入框里的字符串。"""
    if item.kind == "bool":
        return "true" if bool(value) else "false"
    if item.kind == "int":
        return str(int(value))
    if item.kind == "float":
        text = f"{float(value):.6f}".rstrip("0").rstrip(".")
        return text or "0"
    return "" if value is None else str(value)


def _input(item: TaskSettingField) -> Dict[str, Any]:
    label = f"{item.label}（{item.unit}）" if item.unit else item.label
    data: Dict[str, Any] = {"name": item.key, "label": label}
    if item.help:
        data["description"] = item.help
    data["default"] = format_value(item, item.default)
    data["pipeline_type"] = _PIPELINE_TYPES[item.kind]
    if item.kind == "float":
        data["verify"] = NUMBER_VERIFY
        data["pattern_msg"] = "请输入非负数字，例如 35 或 0.5"
    elif item.kind == "int":
        data["verify"] = INT_VERIFY
        data["pattern_msg"] = "请输入非负整数"
    elif item.kind == "bool":
        data["verify"] = BOOL_VERIFY
        data["pattern_msg"] = "请输入 true 或 false"
    return data


def _option(spec: TaskSpec, fields: Sequence[TaskSettingField]) -> Dict[str, Any]:
    param: Dict[str, Any] = {"task": spec.key}
    for item in fields:
        param[item.key] = "{" + item.key + "}"
    return {
        "type": "input",
        "label": f"{spec.name}参数",
        "inputs": [_input(item) for item in fields],
        "pipeline_override": {entry_name(spec.key): {"custom_action_param": param}},
    }


def _task(spec: TaskSpec, has_option: bool) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "name": spec.name,
        "entry": entry_name(spec.key),
        "description": spec.description,
        "default_check": spec.default_enabled,
        "option": [option_name(spec.key)] if has_option else [],
    }
    count = _count_field(spec)
    if count is not None:
        data["repeatable"] = True
        data["repeat_count"] = int(count.default)
    return data


def _preset(
    catalog: Sequence[TaskSpec],
    *,
    name: str,
    description: str,
    enabled_keys: frozenset,
    overrides: Mapping[str, Any],
) -> Dict[str, Any]:
    tasks: List[Dict[str, Any]] = []
    for spec in catalog:
        enabled = spec.key in enabled_keys
        entry: Dict[str, Any] = {"name": spec.name, "enabled": enabled}
        fields = _settable_fields(spec)
        if enabled and fields:
            entry["option"] = {
                option_name(spec.key): {
                    item.key: format_value(item, overrides.get(item.key, item.default))
                    for item in fields
                }
            }
        tasks.append(entry)
    return {"name": name, "label": name, "description": description, "task": tasks}


def build_interface(
    catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG, *, version: str
) -> Dict[str, Any]:
    options: Dict[str, Any] = {}
    tasks: List[Dict[str, Any]] = []
    for spec in catalog:
        fields = _settable_fields(spec)
        if fields:
            options[option_name(spec.key)] = _option(spec, fields)
        tasks.append(_task(spec, bool(fields)))
    presets = [
        _preset(
            catalog,
            name=FORMAL_PRESET_NAME,
            description="勾选每日正式任务，参数取默认值。",
            enabled_keys=FORMAL_PRESET_KEYS,
            overrides={},
        ),
        _preset(
            catalog,
            name=TRIAL_PRESET_NAME,
            description=(
                "勾选阅读、听书、游戏，各 1 分钟，用于冒烟试跑。"
                "预设不能设置重复次数，请把每项的重复次数改为 1。"
            ),
            enabled_keys=TRIAL_PRESET_KEYS,
            overrides={key: 1 for key in _TRIAL_MINUTE_KEYS},
        ),
    ]
    return {
        "interface_version": 2,
        "name": "MaaQQReader",
        "label": TITLE,
        "title": TITLE,
        "version": version,
        "controller": [{"name": "安卓模拟器（ADB）", "type": "Adb", "display_short_side": 720}],
        "resource": [{"name": "QQ阅读", "path": ["./resource"]}],
        "agent": {"child_exec": "python", "child_args": ["-X", "utf8", "./agent/main.py"]},
        "task": tasks,
        "option": options,
        "preset": presets,
    }


def build_pipeline(catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG) -> Dict[str, Any]:
    pipeline: Dict[str, Any] = {}
    for spec in catalog:
        param: Dict[str, Any] = {"task": spec.key}
        for item in _settable_fields(spec):
            param[item.key] = item.default
        pipeline[entry_name(spec.key)] = {
            "action": "Custom",
            "custom_action": ACTION_NAME,
            "custom_action_param": param,
        }
    return pipeline
