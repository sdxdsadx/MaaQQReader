"""QQR-10：运行结果状态、失败原因记录与关键节点截图。

锁定 AGENTS.md §2.4 / §3.9 / §4：

* 结果枚举可区分 SUCCESS / FAILED / TIMEOUT / BLOCKED_BY_CAPTCHA / SKIPPED；
* 识别失败与验证码不会被记成 FAILED；
* 每次任务记录包含任务名、开始/结束时间、结果状态、失败原因、恢复历史
  与关键节点截图路径；
* 记录/截图存放在源码目录之外，保留期可配置（默认 30 天）；
* 截图只是证据，不能单独决定成功。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional, Sequence

from qqreader.contract.conditions import Always, Never, feature
from qqreader.contract.outcome import TaskOutcome
from qqreader.page.features import FeatureKind, FeatureSpec
from qqreader.page.observation import PageObservation
from qqreader.page.states import PageState
from qqreader.recovery.policy import EscalationPolicy
from qqreader.runner.recording import FileRunRecorder, RecordingConfig
from qqreader.runner.runner import RunnerConfig, TaskRunner
from tests.helpers import (
    FakeAdapter,
    FakeClock,
    QueueObserver,
    StubCaptchaGuard,
    captcha_observation,
    make_contract,
    make_definition,
    reward_observation,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nQQR-10-test-screenshot"


class ScreenshotObserver(QueueObserver):
    """在 QueueObserver 基础上提供 save_last_screenshot（模拟 Maa 观测器）。"""

    def __init__(self, script: Sequence[PageObservation]) -> None:
        super().__init__(script)
        self.saved: list[Path] = []

    def save_last_screenshot(self, path: Path) -> Optional[Path]:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG_BYTES)
        self.saved.append(path)
        return path


def _recorder(tmp_path: Path, *, retention_days: int = 30) -> FileRunRecorder:
    return FileRunRecorder(
        RecordingConfig(
            record_dir=tmp_path / "records",
            screenshot_dir=tmp_path / "screenshots",
            retention_days=retention_days,
        )
    )


def _load_record(result) -> dict:  # noqa: ANN001
    assert result.record_path is not None
    return json.loads(Path(result.record_path).read_text(encoding="utf-8"))


def test_recorder_writes_required_fields_and_key_node_screenshots(tmp_path: Path) -> None:
    contract = make_contract(
        name="qqr10_success",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        success_condition=feature(FeatureSpec(kind=FeatureKind.OCR, key="12/12")),
        timeout_seconds=10.0,
    )
    observer = ScreenshotObserver([reward_observation(ocr=("12/12",))])
    recorder = _recorder(tmp_path)

    result = TaskRunner(
        make_definition(contract, observer, FakeAdapter()),
        FakeClock(),
        recorder=recorder,
    ).run()

    assert result.outcome is TaskOutcome.SUCCESS
    assert result.record_path is not None
    assert Path(result.record_path).is_file()

    record = _load_record(result)
    # QQR-10 要求的每次任务记录字段。
    for key in (
        "task",
        "outcome",
        "reason",
        "started_at",
        "ended_at",
        "duration_seconds",
        "steps",
        "final_state",
        "run_state",
        "recovery_history",
        "screenshots",
        "diagnostics",
    ):
        assert key in record, key
    assert record["task"] == "qqr10_success"
    assert record["outcome"] == TaskOutcome.SUCCESS.value

    kinds = [shot["kind"] for shot in record["screenshots"]]
    assert "TASK_START" in kinds
    assert "PAGE_REWARD_HOME" in kinds
    assert "SUCCESS" in kinds
    # 截图路径必须真实存在，且存放在配置的 screenshot_dir 下。
    shot_paths = [Path(shot["path"]) for shot in record["screenshots"] if shot["path"]]
    assert shot_paths
    assert all(path.is_file() for path in shot_paths)
    assert all(str(path).startswith(str(tmp_path / "screenshots")) for path in shot_paths)


def test_failed_task_record_contains_recovery_history(tmp_path: Path) -> None:
    """真正 FAILED 必须能回答「试过哪些恢复、为什么」。"""
    contract = make_contract(
        name="qqr10_failed",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        success_condition=Never(),
        timeout_seconds=12.0,
    )
    observer = ScreenshotObserver([PageObservation.empty()])
    policy = EscalationPolicy(max_rounds=1)
    recorder = _recorder(tmp_path)

    result = TaskRunner(
        make_definition(
            contract,
            observer,
            FakeAdapter(),
            recovery=policy,
        ),
        FakeClock(),
        recorder=recorder,
    ).run()

    assert result.outcome is TaskOutcome.FAILED
    record = _load_record(result)
    actions = [step["action"] for step in record["recovery_history"]]
    assert actions
    assert "GIVE_UP" in actions  # 恢复阶梯耗尽被记录，而不是静默失败
    assert any(shot["kind"].startswith("RECOVERY_") for shot in record["screenshots"])


def test_captcha_is_blocked_by_captcha_not_failed(tmp_path: Path) -> None:
    contract = make_contract(
        name="qqr10_captcha",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        captcha_condition=Always(),
        success_condition=Never(),
        timeout_seconds=30.0,
    )
    observer = ScreenshotObserver([captcha_observation()])
    recorder = _recorder(tmp_path)

    result = TaskRunner(
        make_definition(
            contract,
            observer,
            FakeAdapter(),
            captcha_guard=StubCaptchaGuard(),
        ),
        FakeClock(),
        recorder=recorder,
    ).run()

    assert result.outcome is TaskOutcome.BLOCKED_BY_CAPTCHA
    assert result.outcome is not TaskOutcome.FAILED
    record = _load_record(result)
    assert record["outcome"] == TaskOutcome.BLOCKED_BY_CAPTCHA.value
    kinds = [shot["kind"] for shot in record["screenshots"]]
    assert "CAPTCHA_DETECTED" in kinds
    assert "BLOCKED_BY_CAPTCHA" in kinds


def test_screenshot_evidence_alone_does_not_make_task_success(tmp_path: Path) -> None:
    """success_condition 为 Never 时，即使有截图也必须不是 SUCCESS。"""
    contract = make_contract(
        name="qqr10_evidence_only",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        success_condition=Never(),
        timeout_seconds=10.0,
    )
    observer = ScreenshotObserver([reward_observation()])
    recorder = _recorder(tmp_path)

    result = TaskRunner(
        make_definition(contract, observer, FakeAdapter()),
        FakeClock(),
        recorder=recorder,
        config=RunnerConfig(max_steps=5),
    ).run()

    assert result.outcome is TaskOutcome.FAILED
    assert result.outcome is not TaskOutcome.SUCCESS
    assert result.screenshots
    record = _load_record(result)
    assert record["outcome"] == TaskOutcome.FAILED.value
    assert record["screenshots"]


def test_retention_prunes_old_records_and_screenshots(tmp_path: Path) -> None:
    record_dir = tmp_path / "records"
    screenshot_dir = tmp_path / "screenshots"
    record_dir.mkdir(parents=True)
    screenshot_dir.mkdir(parents=True)
    old_record = record_dir / "old.json"
    old_shot = screenshot_dir / "old.png"
    fresh_record = record_dir / "fresh.json"
    fresh_shot = screenshot_dir / "fresh.png"
    for path in (old_record, old_shot, fresh_record, fresh_shot):
        path.write_bytes(b"x")

    old_time = time.time() - 3 * 86400
    for path in (old_record, old_shot):
        os.utime(path, (old_time, old_time))

    # 构造时即执行一次清理；保留期 1 天。
    FileRunRecorder(
        RecordingConfig(
            record_dir=record_dir,
            screenshot_dir=screenshot_dir,
            retention_days=1,
        )
    )

    assert not old_record.exists()
    assert not old_shot.exists()
    assert fresh_record.exists()
    assert fresh_shot.exists()


def test_recorder_failure_does_not_change_task_outcome(tmp_path: Path) -> None:
    """记录器自身抛错时，任务结果仍由契约决定，并留下 record.error 诊断。"""
    class BrokenRecorder:
        def start(self, context):  # noqa: ANN001
            raise RuntimeError("start broken")

        def capture(self, context, kind, note, provider=None):  # noqa: ANN001
            raise RuntimeError("capture broken")

        def recovery(self, context, step):  # noqa: ANN001
            raise RuntimeError("recovery broken")

        def finish(self, result):  # noqa: ANN001
            raise RuntimeError("finish broken")

    contract = make_contract(
        name="qqr10_broken_recorder",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        success_condition=feature(FeatureSpec(kind=FeatureKind.OCR, key="12/12")),
        timeout_seconds=10.0,
    )
    result = TaskRunner(
        make_definition(contract, QueueObserver([reward_observation(ocr=("12/12",))]), FakeAdapter()),
        FakeClock(),
        recorder=BrokenRecorder(),
    ).run()

    assert result.outcome is TaskOutcome.SUCCESS
    assert any(event.kind == "record.error" for event in result.diagnostics)


def test_task_outcome_enum_has_required_statuses() -> None:
    required = {"SUCCESS", "FAILED", "TIMEOUT", "BLOCKED_BY_CAPTCHA", "SKIPPED"}
    assert required.issubset({outcome.value for outcome in TaskOutcome})
