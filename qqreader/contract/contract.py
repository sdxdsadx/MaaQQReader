"""任务契约：每个任务必须显式定义的 8 个字段（AGENTS.md §3.3）。

``TaskContract`` 是**纯数据**：它只描述「什么算起点 / 就绪 / 推进 / 验证码 /
成功 / 可恢复错误 / 致命错误 / 超时」，不包含任何点击或识别实现。具体行为
由注入的适配器提供，因此调度核心不需要对任务名做任何特判。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from ..errors import ContractViolation
from .conditions import Condition

#: AGENTS.md §3.3 明文要求的 8 个契约字段（顺序即文档顺序）。
CONTRACT_FIELDS: Tuple[str, ...] = (
    "start_condition",
    "ready_condition",
    "progress_condition",
    "captcha_condition",
    "success_condition",
    "recoverable_error",
    "fatal_error",
    "timeout",
)

_FIELD_DOC = {
    "start_condition": "从哪个可预测的公共起点开始",
    "ready_condition": "目标页面/进程确实就绪",
    "progress_condition": "仍在正常推进",
    "captcha_condition": "何时判定进入验证码状态",
    "success_condition": "以什么为唯一正常完成标志",
    "recoverable_error": "哪些异常可恢复，如何恢复",
    "fatal_error": "哪些异常直接失败",
    "timeout": "独立超时",
}


@dataclass(frozen=True)
class TimeoutSpec:
    """任务的独立超时。"""

    seconds: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.seconds <= 0:
            raise ContractViolation("timeout.seconds 必须 > 0")

    def describe(self) -> str:
        return f"timeout={self.seconds:g}s" + (f" ({self.label})" if self.label else "")


@dataclass(frozen=True)
class RecoverableErrorSpec:
    """一条可恢复异常。恢复动作由恢复策略决定（见 ``recovery/``）。"""

    name: str
    when: Condition
    hint: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ContractViolation("RecoverableErrorSpec.name 不能为空")


@dataclass(frozen=True)
class FatalErrorSpec:
    """一条致命异常：判定后任务结果为 ``FAILED``。"""

    name: str
    when: Condition
    hint: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ContractViolation("FatalErrorSpec.name 不能为空")


@dataclass(frozen=True)
class TaskContract:
    """任务契约（8 字段）。"""

    name: str
    start_condition: Condition
    ready_condition: Condition
    progress_condition: Condition
    captcha_condition: Condition
    success_condition: Condition
    recoverable_error: Tuple[RecoverableErrorSpec, ...]
    fatal_error: Tuple[FatalErrorSpec, ...]
    timeout: TimeoutSpec
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ContractViolation("TaskContract.name 不能为空")
        if not isinstance(self.timeout, TimeoutSpec):
            raise ContractViolation("TaskContract.timeout 必须是 TimeoutSpec")
        for name in CONTRACT_FIELDS:
            if getattr(self, name) is None:
                raise ContractViolation(f"任务契约缺少字段: {name}")

    # 复数别名，便于阅读；底层字段名与 AGENTS.md §3.3 完全一致。
    @property
    def recoverable_errors(self) -> Tuple[RecoverableErrorSpec, ...]:
        return self.recoverable_error

    @property
    def fatal_errors(self) -> Tuple[FatalErrorSpec, ...]:
        return self.fatal_error

    @classmethod
    def required_fields(cls) -> Tuple[str, ...]:
        return CONTRACT_FIELDS

    def field_report(self) -> Mapping[str, str]:
        """返回字段名 → 语义说明，供文档与测试核对。"""
        return {name: _FIELD_DOC[name] for name in CONTRACT_FIELDS}

    def describe(self) -> str:
        lines = [f"任务契约 {self.name}" + (f" — {self.description}" if self.description else "")]
        lines.append(f"  start_condition      : {self.start_condition.describe()}")
        lines.append(f"  ready_condition      : {self.ready_condition.describe()}")
        lines.append(f"  progress_condition   : {self.progress_condition.describe()}")
        lines.append(f"  captcha_condition    : {self.captcha_condition.describe()}")
        lines.append(f"  success_condition    : {self.success_condition.describe()}")
        recoverable = ", ".join(e.name for e in self.recoverable_error) or "(无)"
        fatal = ", ".join(e.name for e in self.fatal_error) or "(无)"
        lines.append(f"  recoverable_error    : {recoverable}")
        lines.append(f"  fatal_error          : {fatal}")
        lines.append(f"  timeout              : {self.timeout.describe()}")
        return "\n".join(lines)
