"""每日任务流水线的配置快照、运行状态与持久化记录。

任务内部仍由 ``run_task.py`` 负责；本模块只管理任务之间的严格串行、
失败后继续、用户停止和流水线级证据。设计语义与 Gameflow 的流水线一致，
但不引入其桌面运行时或存储依赖。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from .runner.exit_codes import EXIT_BLOCKED_BY_CAPTCHA, EXIT_SUCCESS, describe_exit_code


CHINA_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
BUSINESS_DAY_BOUNDARY_HOUR = 4


def business_day(at: datetime) -> date:
    """返回北京时间 04:00 切换的业务日。"""
    if at.tzinfo is None:
        at = at.astimezone()
    china_time = at.astimezone(CHINA_TIMEZONE)
    return (china_time - timedelta(hours=BUSINESS_DAY_BOUNDARY_HOUR)).date()


class FlowStepState(str, Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED_BY_CAPTCHA = "BLOCKED_BY_CAPTCHA"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class FlowRunState(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    #: QQR-53：验证码未解决，后续任务全部跳过，等待人工。
    BLOCKED_BY_CAPTCHA = "BLOCKED_BY_CAPTCHA"
    CANCELLED = "CANCELLED"


def _freeze_settings(settings: Mapping[str, Any]) -> Tuple[Tuple[str, Any], ...]:
    return tuple(sorted(((str(key), value) for key, value in settings.items())))


@dataclass(frozen=True)
class FlowStepSnapshot:
    """本轮开始时冻结的一项任务配置。"""

    step_id: str
    task_key: str
    display_name: str
    repeat_index: int = 1
    repeat_total: int = 1
    settings: Tuple[Tuple[str, Any], ...] = ()

    @classmethod
    def create(
        cls,
        *,
        step_id: str,
        task_key: str,
        display_name: str,
        settings: Optional[Mapping[str, Any]] = None,
        repeat_index: int = 1,
        repeat_total: int = 1,
    ) -> "FlowStepSnapshot":
        if not step_id.strip() or not task_key.strip() or not display_name.strip():
            raise ValueError("step_id、task_key 和 display_name 不能为空")
        if repeat_index < 1 or repeat_total < repeat_index:
            raise ValueError("重复序号必须满足 1 <= repeat_index <= repeat_total")
        return cls(
            step_id=step_id,
            task_key=task_key,
            display_name=display_name,
            repeat_index=repeat_index,
            repeat_total=repeat_total,
            settings=_freeze_settings(settings or {}),
        )

    def settings_dict(self) -> dict[str, Any]:
        return dict(self.settings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "task_key": self.task_key,
            "display_name": self.display_name,
            "repeat_index": self.repeat_index,
            "repeat_total": self.repeat_total,
            "settings": self.settings_dict(),
        }


@dataclass
class FlowStepRecord:
    snapshot: FlowStepSnapshot
    state: FlowStepState = FlowStepState.WAITING
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    reason: str = ""
    #: 由退出码解释出的任务结果（成功 / 验证码阻塞 / 超时 / 设备错误……）。
    outcome: str = ""
    #: QQR-53：启动本项之前的交接检查结果（结论、原因、动作、页面证据）。
    handoff: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.snapshot.to_dict(),
            "state": self.state.value,
            "started_at": _iso(self.started_at),
            "ended_at": _iso(self.ended_at),
            "exit_code": self.exit_code,
            "outcome": self.outcome,
            "reason": self.reason,
            "handoff": self.handoff,
        }


@dataclass
class DailyFlowRun:
    run_id: str
    business_day: date
    captured_at: datetime
    config_path: str
    steps: list[FlowStepRecord]
    state: FlowRunState = FlowRunState.RUNNING
    ended_at: Optional[datetime] = None

    @classmethod
    def start(
        cls,
        snapshots: Sequence[FlowStepSnapshot],
        *,
        config_path: str = "",
        at: Optional[datetime] = None,
        run_id: Optional[str] = None,
    ) -> "DailyFlowRun":
        if not snapshots:
            raise ValueError("流水线至少需要一个任务")
        if len({item.step_id for item in snapshots}) != len(snapshots):
            raise ValueError("流水线 step_id 不能重复")
        started = at or datetime.now(timezone.utc)
        run = cls(
            run_id=run_id or _new_run_id(started),
            business_day=business_day(started),
            captured_at=started,
            config_path=config_path,
            steps=[FlowStepRecord(item) for item in snapshots],
        )
        run.start_next(started)
        return run

    @property
    def current(self) -> Optional[FlowStepRecord]:
        running = [step for step in self.steps if step.state is FlowStepState.RUNNING]
        if len(running) > 1:
            raise RuntimeError("流水线同一时间只能运行一个任务")
        return running[0] if running else None

    @property
    def next_waiting(self) -> Optional[FlowStepRecord]:
        return next(
            (step for step in self.steps if step.state is FlowStepState.WAITING),
            None,
        )

    def start_next(
        self,
        at: Optional[datetime] = None,
        *,
        handoff: Optional[Mapping[str, Any]] = None,
    ) -> FlowStepRecord:
        self._ensure_running()
        if self.current is not None:
            raise RuntimeError("当前任务尚未结束")
        next_step = self.next_waiting
        if next_step is None:
            raise RuntimeError("没有等待中的任务")
        next_step.state = FlowStepState.RUNNING
        next_step.started_at = at or datetime.now(timezone.utc)
        if handoff is not None:
            next_step.handoff = dict(handoff)
        return next_step

    def complete_current(
        self,
        exit_code: int,
        *,
        reason: str = "",
        at: Optional[datetime] = None,
    ) -> FlowStepRecord:
        self._ensure_running()
        current = self.current
        if current is None:
            raise RuntimeError("没有正在运行的任务")
        ended = at or datetime.now(timezone.utc)
        current.exit_code = int(exit_code)
        current.outcome = describe_exit_code(int(exit_code))
        current.reason = reason or (
            "任务证据确认成功"
            if exit_code == EXIT_SUCCESS
            else f"子进程退出码 {exit_code}（{current.outcome}）"
        )
        current.ended_at = ended
        if exit_code == EXIT_SUCCESS:
            current.state = FlowStepState.SUCCEEDED
        elif exit_code == EXIT_BLOCKED_BY_CAPTCHA:
            # 验证码没解决：后续任务一律不启动（QQR-53）。
            current.state = FlowStepState.BLOCKED_BY_CAPTCHA
            self._block_remaining(f"前项 {current.snapshot.display_name} 被验证码阻塞", ended)
            return current
        else:
            current.state = FlowStepState.FAILED
        self._finish_if_done(ended)
        return current

    def skip_next(
        self,
        reason: str,
        *,
        handoff: Optional[Mapping[str, Any]] = None,
        at: Optional[datetime] = None,
    ) -> FlowStepRecord:
        """交接检查无法确认安全起点：不启动下一项，记为 SKIPPED 并保留原因。"""
        self._ensure_running()
        if self.current is not None:
            raise RuntimeError("当前任务尚未结束")
        step = self.next_waiting
        if step is None:
            raise RuntimeError("没有等待中的任务")
        skipped = at or datetime.now(timezone.utc)
        step.state = FlowStepState.SKIPPED
        step.ended_at = skipped
        step.reason = reason
        step.outcome = "跳过"
        if handoff is not None:
            step.handoff = dict(handoff)
        self._finish_if_done(skipped)
        return step

    def block_by_captcha(
        self,
        reason: str,
        *,
        handoff: Optional[Mapping[str, Any]] = None,
        at: Optional[datetime] = None,
    ) -> None:
        """交接检查发现验证码：剩余任务全部跳过，流水线停在验证码阻塞。"""
        self._ensure_running()
        if self.current is not None:
            raise RuntimeError("当前任务尚未结束")
        step = self.next_waiting
        if step is not None and handoff is not None:
            step.handoff = dict(handoff)
        self._block_remaining(reason, at or datetime.now(timezone.utc))

    def _block_remaining(self, reason: str, at: datetime) -> None:
        for step in self.steps:
            if step.state is FlowStepState.WAITING:
                step.state = FlowStepState.SKIPPED
                step.ended_at = at
                step.outcome = "跳过"
                step.reason = f"因验证码阻塞而跳过：{reason}；等待人工处理"
        self.state = FlowRunState.BLOCKED_BY_CAPTCHA
        self.ended_at = at

    def _finish_if_done(self, at: datetime) -> None:
        if self.next_waiting is not None:
            return
        self.state = (
            FlowRunState.SUCCEEDED
            if all(step.state is FlowStepState.SUCCEEDED for step in self.steps)
            else FlowRunState.COMPLETED_WITH_ERRORS
        )
        self.ended_at = at

    def stop_by_user(
        self,
        *,
        reason: str = "用户停止流水线",
        at: Optional[datetime] = None,
    ) -> None:
        self._ensure_running()
        stopped = at or datetime.now(timezone.utc)
        current = self.current
        if current is not None:
            current.state = FlowStepState.CANCELLED
            current.ended_at = stopped
            current.reason = reason
        for step in self.steps:
            if step.state is FlowStepState.WAITING:
                step.state = FlowStepState.SKIPPED
                step.ended_at = stopped
                step.reason = "因用户停止流水线而跳过"
        self.state = FlowRunState.CANCELLED
        self.ended_at = stopped

    def counts(self) -> dict[str, int]:
        return {
            state.value: sum(step.state is state for step in self.steps)
            for state in FlowStepState
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_version": 2,
            "run_id": self.run_id,
            "business_day": self.business_day.isoformat(),
            "captured_at": _iso(self.captured_at),
            "ended_at": _iso(self.ended_at),
            "config_path": self.config_path,
            "state": self.state.value,
            "counts": self.counts(),
            "steps": [step.to_dict() for step in self.steps],
        }

    def _ensure_running(self) -> None:
        if self.state is not FlowRunState.RUNNING:
            raise RuntimeError(f"流水线状态为 {self.state.value}，不能再修改")


class DailyFlowRecorder:
    """在每次状态变化后原子写入同一份流水线 JSON。"""

    def __init__(self, record_dir: Path) -> None:
        self.record_dir = Path(record_dir)

    def path_for(self, run: DailyFlowRun) -> Path:
        return self.record_dir / "daily_flows" / f"{run.run_id}.json"

    def save(self, run: DailyFlowRun) -> Path:
        target = self.path_for(run)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(run.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
        return target


def handoff_report_path(record_dir: Path, run: DailyFlowRun) -> Path:
    """下一项任务交接检查的报告文件（与流水线记录放在一起）。"""
    step = run.next_waiting
    suffix = step.snapshot.step_id if step is not None else "end"
    return Path(record_dir) / "daily_flows" / f"{run.run_id}_handoff_{suffix}.json"


def load_handoff_report(path: Path) -> dict[str, Any]:
    """读取交接检查写出的 JSON；缺失或损坏时返回空字典（原因写进记录）。"""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"report_error": f"{type(exc).__name__}: {exc}"}
    return data if isinstance(data, dict) else {"report_error": "报告不是 JSON 对象"}


def apply_handoff(
    run: DailyFlowRun,
    exit_code: int,
    report: Optional[Mapping[str, Any]] = None,
) -> Optional[FlowStepRecord]:
    """按交接检查结果决定下一项：启动 / 跳过 / 验证码阻塞（GUI 与 daily_all 共用）。

    返回已启动的步骤；跳过或阻塞时返回 ``None``。前项的结果不参与放行判断——
    前项失败但现场已确认安全可以继续，前项成功但现场不安全也不能继续。
    """
    detail = {"exit_code": int(exit_code), **dict(report or {})}
    previous = next(
        (
            step
            for step in reversed(run.steps)
            if step.state not in (FlowStepState.WAITING, FlowStepState.RUNNING)
        ),
        None,
    )
    previous_text = (
        f"前项 {previous.snapshot.display_name}："
        f"{previous.outcome or previous.state.value}"
        if previous is not None
        else "前项：无"
    )
    detail["previous"] = previous_text
    if exit_code == EXIT_SUCCESS:
        return run.start_next(handoff=detail)
    if exit_code == EXIT_BLOCKED_BY_CAPTCHA:
        run.block_by_captcha(f"交接检查发现验证码（{previous_text}）", handoff=detail)
        return None
    why = detail.get("reason") or describe_exit_code(int(exit_code))
    run.skip_next(f"交接失败，未启动：{why}（{previous_text}）", handoff=detail)
    return None


def snapshots_from_plans(plans: Iterable[Any]) -> tuple[FlowStepSnapshot, ...]:
    """把 GUI 的 ``TaskRunPlan`` 转成与后续设置修改隔离的快照。"""
    snapshots = []
    for index, plan in enumerate(plans, start=1):
        snapshots.append(
            FlowStepSnapshot.create(
                step_id=f"{index:02d}-{plan.spec.key}-{plan.repeat_index}",
                task_key=plan.spec.key,
                display_name=plan.spec.display_name,
                settings=dict(plan.settings.values),
                repeat_index=plan.repeat_index,
                repeat_total=plan.repeat_total,
            )
        )
    return tuple(snapshots)


def _new_run_id(at: datetime) -> str:
    stamp = at.astimezone(CHINA_TIMEZONE).strftime("%Y%m%d_%H%M%S")
    return f"daily_{stamp}_{uuid4().hex[:8]}"


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None
