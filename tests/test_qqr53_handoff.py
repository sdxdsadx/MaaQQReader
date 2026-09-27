"""QQR-53：串行交接必须确认现场；验证码阻塞不得继续排下一项。

识别相关用例全部使用 ``tests/fixtures/handoff_ocr_frames.json`` 中的真实 OCR 帧
（从 ``runtime/logs/maafw*.log`` 的 OCRer 结果原样抽取，来源写在每帧的 source 字段）。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List, Mapping, Sequence, Tuple

import pytest

from qqreader.contract.outcome import TaskOutcome
from qqreader.gui.app import QQReaderGui
from qqreader.gui.task_catalog import DEFAULT_TASK_CATALOG, TaskRunPlan, default_settings
from qqreader.maa import RecoResult
from qqreader.runner.exit_codes import (
    EXIT_BLOCKED_BY_CAPTCHA,
    EXIT_DEVICE_ERROR,
    EXIT_FAILED,
    EXIT_HANDOFF_UNSAFE,
    EXIT_SUCCESS,
    EXIT_TIMEOUT,
    exit_code_for_outcome,
)
from qqreader.runner.handoff import (
    FrameKind,
    HandoffVerdict,
    check_handoff,
    classify_frame,
)
from qqreader.workflow import (
    DailyFlowRun,
    FlowRunState,
    FlowStepSnapshot,
    FlowStepState,
    apply_handoff,
)

Box = Tuple[int, int, int, int]
Frame = List[Tuple[str, Box]]

_FIXTURE = Path(__file__).parent / "fixtures" / "handoff_ocr_frames.json"
FRAMES = json.loads(_FIXTURE.read_text(encoding="utf-8"))


def frame(name: str) -> Frame:
    return [(text, tuple(box)) for text, box in FRAMES[name]["boxes"]]


def bookstore_without_dialog() -> Frame:
    """同一张书城排行榜截图去掉升级弹窗的文字（弹窗取消后的样子）。"""
    dialog = {"安装新版本", "安装", "已下载新版本，是否安装？", "V8.5.6", "取消"}
    return [item for item in frame("bookstore_upgrade_dialog") if item[0] not in dialog]


class FakeShot:
    def __init__(self, boxes: Frame) -> None:
        self.boxes = boxes

    def save(self, path: Path) -> Path:
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return Path(path)


class FakeClient:
    def __init__(self, frames: Sequence[Frame]) -> None:
        self.frames = list(frames)
        self.index = 0
        self.clicks: List[Tuple[int, int]] = []
        self.keys: List[int] = []
        self.stopped: List[str] = []
        self.started: List[str] = []

    def screencap(self) -> FakeShot:
        shot = FakeShot(self.frames[min(self.index, len(self.frames) - 1)])
        self.index += 1
        return shot

    def recognize(self, reco_type: str, params: Mapping[str, Any], shot: FakeShot) -> RecoResult:
        assert reco_type == "OCR"
        return RecoResult(
            "OCR",
            bool(shot.boxes),
            detail={"all": [{"text": t, "box": list(b), "score": 0.99} for t, b in shot.boxes]},
        )

    def click(self, x: int, y: int) -> bool:
        self.clicks.append((x, y))
        return True

    def click_key(self, keycode: int) -> bool:
        self.keys.append(keycode)
        return True

    def stop_app(self, package: str) -> bool:
        self.stopped.append(package)
        return True

    def start_app(self, package: str) -> bool:
        self.started.append(package)
        return True


def run_check(client: FakeClient, **kwargs: Any):
    return check_handoff(
        client, package="com.qq.reader", settle_seconds=0, restart_wait_seconds=0, **kwargs
    )


# ------------------------------------------------------------------ 页面分类


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("retention_popup", FrameKind.AD_RETENTION),
        ("shelf", FrameKind.SHELF),
        ("bookstore_upgrade_dialog", FrameKind.UPGRADE_DIALOG),
        ("shelf_exit_dialog", FrameKind.EXIT_DIALOG),
        ("captcha_over_reward", FrameKind.CAPTCHA),
    ],
)
def test_real_frames_are_classified(name: str, expected: FrameKind) -> None:
    assert classify_frame(frame(name)) is expected


def test_bookstore_ranking_page_is_not_shelf() -> None:
    """书城排行榜页不能被确认成书架（QQR-55 同一现场）。"""
    assert classify_frame(bookstore_without_dialog()) is FrameKind.BOOKSTORE


def test_reward_page_is_not_shelf_even_with_reread_text() -> None:
    reward = [item for item in frame("captcha_over_reward") if "验证" not in item[0] and "拼图" not in item[0]]
    assert classify_frame(reward) is not FrameKind.SHELF


# ------------------------------------------------------------------ 交接动作


def test_level_ad_retention_popup_gives_up_then_confirms_shelf(tmp_path: Path) -> None:
    """2026-09-27 现场：挽留弹窗 → 点「放弃奖励」→ 重新截图确认书架。"""
    client = FakeClient([frame("retention_popup"), frame("shelf")])
    result = run_check(client, evidence_dir=tmp_path)
    assert result.verdict is HandoffVerdict.READY
    assert client.clicks == [(358, 858)]  # 「放弃奖励」box=(299,840,119,37) 的中心
    assert client.keys == []
    assert result.evidence is not None and result.evidence.is_file()


def test_captcha_stops_handoff_without_any_action() -> None:
    client = FakeClient([frame("captcha_over_reward")])
    result = run_check(client)
    assert result.verdict is HandoffVerdict.CAPTCHA
    assert (client.clicks, client.keys, client.stopped, client.started) == ([], [], [], [])


def test_captcha_after_back_stops_immediately() -> None:
    client = FakeClient([[("广告", (657, 1208, 33, 20))], frame("captcha_over_reward"), frame("shelf")])
    result = run_check(client)
    assert result.verdict is HandoffVerdict.CAPTCHA
    assert client.keys == [4]
    assert client.stopped == [] and client.started == []


def test_upgrade_dialog_then_bookstore_goes_to_shelf_tab() -> None:
    client = FakeClient([frame("bookstore_upgrade_dialog"), bookstore_without_dialog(), frame("shelf")])
    result = run_check(client)
    assert result.verdict is HandoffVerdict.READY
    # 先点「取消」(510,1226,56,32)，绝不点「安装」；再点底部书架 tab。
    assert client.clicks[0] == (538, 1242)
    assert len(client.clicks) == 2


def test_unrecoverable_page_backs_restarts_once_then_unsafe() -> None:
    stuck = [("广告", (657, 1208, 33, 20)), ("了解详情", (308, 1120, 106, 32))]
    client = FakeClient([stuck])
    result = run_check(client, max_backs=2)
    assert result.verdict is HandoffVerdict.UNSAFE
    assert client.keys == [4, 4, 4, 4]  # 重启前 2 次 + 重启后 2 次
    assert client.stopped == ["com.qq.reader"] and client.started == ["com.qq.reader"]
    assert "重启" in result.reason


# ------------------------------------------------------------------ 退出码与流水线语义


def test_non_success_outcomes_have_distinct_exit_codes() -> None:
    codes = {outcome: exit_code_for_outcome(outcome) for outcome in TaskOutcome}
    assert codes[TaskOutcome.SUCCESS] == EXIT_SUCCESS
    assert codes[TaskOutcome.FAILED] == EXIT_FAILED
    assert codes[TaskOutcome.BLOCKED_BY_CAPTCHA] == EXIT_BLOCKED_BY_CAPTCHA
    assert codes[TaskOutcome.TIMEOUT] == EXIT_TIMEOUT
    assert codes[TaskOutcome.DEVICE_ERROR] == EXIT_DEVICE_ERROR
    distinct = {codes[o] for o in (TaskOutcome.FAILED, TaskOutcome.BLOCKED_BY_CAPTCHA,
                                   TaskOutcome.TIMEOUT, TaskOutcome.DEVICE_ERROR)}
    assert len(distinct) == 4


def _run(*keys: str) -> DailyFlowRun:
    return DailyFlowRun.start(
        [FlowStepSnapshot.create(step_id=f"{i}-{k}", task_key=k, display_name=k)
         for i, k in enumerate(keys, start=1)]
    )


def test_captcha_exit_blocks_all_remaining_steps() -> None:
    run = _run("DailyLevelAdFlow", "DailyAudiobookFlow", "DailyGameFlow")
    run.complete_current(EXIT_BLOCKED_BY_CAPTCHA)
    assert run.state is FlowRunState.BLOCKED_BY_CAPTCHA
    assert [s.state for s in run.steps] == [
        FlowStepState.BLOCKED_BY_CAPTCHA, FlowStepState.SKIPPED, FlowStepState.SKIPPED,
    ]
    assert "验证码" in run.steps[1].reason


def test_failed_previous_but_confirmed_scene_may_continue() -> None:
    run = _run("DailyLevelAdFlow", "DailyAudiobookFlow")
    run.complete_current(EXIT_FAILED)
    started = apply_handoff(run, EXIT_SUCCESS, {"verdict": "READY", "reason": "已确认在书架"})
    assert started is run.steps[1] and started.state is FlowStepState.RUNNING
    assert started.handoff["previous"].startswith("前项 DailyLevelAdFlow")


def test_successful_previous_but_unsafe_scene_skips_next() -> None:
    run = _run("DailyAdFlow", "DailyAudiobookFlow", "DailyGameFlow")
    run.complete_current(EXIT_SUCCESS)
    started = apply_handoff(run, EXIT_HANDOFF_UNSAFE, {"verdict": "UNSAFE", "reason": "最后页面类型 OTHER"})
    assert started is None
    assert run.steps[1].state is FlowStepState.SKIPPED
    assert "交接失败" in run.steps[1].reason and "最后页面类型 OTHER" in run.steps[1].reason
    assert run.state is FlowRunState.RUNNING  # 下一项仍有自己的交接检查
    assert run.to_dict()["steps"][1]["handoff"]["verdict"] == "UNSAFE"


def test_handoff_captcha_blocks_run() -> None:
    run = _run("DailyAdFlow", "DailyAudiobookFlow", "DailyGameFlow")
    run.complete_current(EXIT_SUCCESS)
    assert apply_handoff(run, EXIT_BLOCKED_BY_CAPTCHA, {"verdict": "CAPTCHA"}) is None
    assert run.state is FlowRunState.BLOCKED_BY_CAPTCHA
    assert all(s.state is FlowStepState.SKIPPED for s in run.steps[1:])


# ------------------------------------------------------------------ GUI 故障注入


class _Var:
    def __init__(self, value: Any = "") -> None:
        self.value = value

    def set(self, value: Any) -> None:
        self.value = value

    def get(self) -> Any:
        return self.value


def _gui(tmp_path: Path, keys: Sequence[str]) -> QQReaderGui:
    gui = QQReaderGui.__new__(QQReaderGui)
    specs = {spec.key: spec for spec in DEFAULT_TASK_CATALOG}
    settings = default_settings()
    gui._serial_plan = [
        TaskRunPlan(spec=specs[k], settings=settings[k].normalized(specs[k])) for k in keys
    ]
    gui._serial_run = DailyFlowRun.start(
        [FlowStepSnapshot.create(step_id=f"{i}-{k}", task_key=k, display_name=k)
         for i, k in enumerate(keys, start=1)]
    )
    gui._serial_recorder = None
    gui._serial_record_path = None
    gui._serial_index = 0
    gui._stopping = False
    gui._run_started_at = None
    gui._progress_var = _Var(0)
    gui._interval_var = _Var("0")
    gui._config_var = _Var(str(tmp_path / "config.json"))
    gui.repo_root = tmp_path
    gui.logs: List[str] = []
    gui._log = gui.logs.append
    gui._set_current = lambda text: None
    gui._set_status = lambda text: None
    config = SimpleNamespace(machine=SimpleNamespace(record_dir=str(tmp_path), python_executable="python"))
    gui._require_config = lambda: config
    gui.processes: List[Tuple[Tuple[str, ...], Any]] = []
    gui._start_process = lambda command, status, on_finish: gui.processes.append((tuple(command), on_finish))
    gui.root = SimpleNamespace(after=lambda ms, callback: callback())
    return gui


def _task_of(command: Sequence[str]) -> str:
    return command[list(command).index("--task") + 1]


def test_gui_level_ad_failure_runs_handoff_before_audiobook(tmp_path: Path) -> None:
    """前项 exit 2 后不得立即启动听书，必须先跑交接检查。"""
    gui = _gui(tmp_path, ["DailyLevelAdFlow", "DailyAudiobookFlow"])
    gui._on_task_finished(EXIT_FAILED)
    assert [_task_of(c) for c, _ in gui.processes] == ["HandoffCheck"]
    command, on_finish = gui.processes[-1]
    assert command[command.index("--next-task") + 1] == "DailyAudiobookFlow"
    assert gui._serial_run.steps[1].state is FlowStepState.WAITING

    # 交接检查无法确认书架 → 听书跳过，不启动。
    report = Path(command[command.index("--handoff-report") + 1])
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"verdict": "UNSAFE", "reason": "仍停在广告页"}, ensure_ascii=False), encoding="utf-8")
    on_finish(EXIT_HANDOFF_UNSAFE)
    assert [_task_of(c) for c, _ in gui.processes] == ["HandoffCheck"]
    audiobook = gui._serial_run.steps[1]
    assert audiobook.state is FlowStepState.SKIPPED
    assert "仍停在广告页" in audiobook.reason and "DailyLevelAdFlow" in audiobook.reason


def test_gui_starts_next_only_after_handoff_ready(tmp_path: Path) -> None:
    gui = _gui(tmp_path, ["DailyLevelAdFlow", "DailyAudiobookFlow"])
    gui._on_task_finished(EXIT_FAILED)
    _command, on_finish = gui.processes[-1]
    on_finish(EXIT_SUCCESS)
    assert [_task_of(c) for c, _ in gui.processes] == ["HandoffCheck", "DailyAudiobookFlow"]
    assert gui._serial_run.steps[1].state is FlowStepState.RUNNING


def test_gui_captcha_exit_starts_nothing_else(tmp_path: Path) -> None:
    gui = _gui(tmp_path, ["DailyAdFlow", "DailyAudiobookFlow", "DailyGameFlow"])
    gui._on_task_finished(EXIT_BLOCKED_BY_CAPTCHA)
    assert gui.processes == []
    assert gui._serial_run.state is FlowRunState.BLOCKED_BY_CAPTCHA
    assert any("验证码" in line for line in gui.logs)


def test_gui_handoff_captcha_stops_run(tmp_path: Path) -> None:
    gui = _gui(tmp_path, ["DailyAdFlow", "DailyAudiobookFlow", "DailyGameFlow"])
    gui._on_task_finished(EXIT_SUCCESS)
    _command, on_finish = gui.processes[-1]
    on_finish(EXIT_BLOCKED_BY_CAPTCHA)
    assert [_task_of(c) for c, _ in gui.processes] == ["HandoffCheck"]
    assert gui._serial_run.state is FlowRunState.BLOCKED_BY_CAPTCHA
