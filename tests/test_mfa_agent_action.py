"""MFAAvalonia Agent 动作逻辑：参数解析、交接检查 + 任务子进程、停止与记录。

子进程全部用可脚本化的假 ``popen`` 代替，不连接设备；``kill_tree`` 也是假的，
只记录被结束的 pid，确保停止时只结束本动作自己启动的进程。
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional

import pytest

from qqreader.mfa.agent_action import (
    ACTION_NAME,
    DEFAULT_CONFIG_RELATIVE,
    RunResult,
    TaskRunner,
    parse_param,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeProcess:
    """可脚本化的子进程：``code`` 为 None 表示永不自行结束（直到被 kill）。"""

    def __init__(self, pid: int, code: Optional[int], lines: Iterable[bytes] = ()) -> None:
        self.pid = pid
        self._code = code
        self.returncode: Optional[int] = None
        self.stdout = io.BytesIO(b"".join(lines))
        self.killed = False

    def poll(self) -> Optional[int]:
        if self._code is not None:
            self.returncode = self._code
        return self.returncode

    def wait(self, timeout: Optional[float] = None) -> int:
        code = self.poll()
        if code is None:
            raise subprocess.TimeoutExpired("fake", timeout or 0)
        return code

    def kill_now(self) -> None:
        self.killed = True
        self._code = 1


class FakePopen:
    def __init__(self, processes: List[FakeProcess]) -> None:
        self.processes = list(processes)
        self.calls: List[tuple] = []
        self.kwargs: List[dict] = []

    def __call__(self, command, **kwargs: Any) -> FakeProcess:
        self.calls.append(tuple(command))
        self.kwargs.append(kwargs)
        return self.processes.pop(0)


class FakeKill:
    def __init__(self, popen: FakePopen, started: List[FakeProcess]) -> None:
        self.pids: List[int] = []
        self._by_pid = {proc.pid: proc for proc in started}

    def __call__(self, pid: int) -> None:
        self.pids.append(pid)
        self._by_pid[pid].kill_now()


def write_config(tmp_path: Path) -> Path:
    config = {
        "version": 1,
        "machine": {
            "adb_path": "adb",
            "adb_address": "127.0.0.1:16384",
            "record_dir": str(tmp_path / "records"),
            "screenshot_dir": str(tmp_path / "shots"),
            "log_dir": str(tmp_path / "logs"),
        },
    }
    path = tmp_path / "qqreader.local.json"
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return path


def make_runner(
    tmp_path: Path,
    processes: List[FakeProcess],
    *,
    is_stopping=lambda: False,
    config_path: Optional[Path] = None,
):
    popen = FakePopen(processes)
    kill = FakeKill(popen, processes)
    logs: List[str] = []
    runner = TaskRunner(
        REPO_ROOT,
        config_path if config_path is not None else write_config(tmp_path),
        popen=popen,
        log=logs.append,
        is_stopping=is_stopping,
        kill_tree=kill,
        poll_interval=0.01,
    )
    return runner, popen, kill, logs


def reading(**overrides: Any):
    return parse_param({"task": "DailyReadingFlow", "minutes": 1, **overrides})


# ------------------------------------------------------------------ 常量


def test_constants():
    assert ACTION_NAME == "QQReaderRunTask"
    assert DEFAULT_CONFIG_RELATIVE == Path("configs/qqreader.local.json")


# ------------------------------------------------------------------ parse_param


def test_parse_param_normalizes_minutes():
    spec, values = parse_param('{"task":"DailyReadingFlow","minutes":"1"}')
    assert spec.key == "DailyReadingFlow"
    assert values["minutes"] == 1.0
    assert values["book_title"] == "宇智波"
    assert "count" not in values


def test_parse_param_ignores_count():
    _, values = parse_param({"task": "DailyReadingFlow", "count": 5})
    assert "count" not in values


def test_parse_param_rejects_unknown_task():
    with pytest.raises(ValueError):
        parse_param('{"task":"NoSuchTask"}')


def test_parse_param_rejects_missing_task():
    with pytest.raises(ValueError):
        parse_param("{}")


def test_parse_param_rejects_unknown_key():
    with pytest.raises(ValueError):
        parse_param({"task": "DailyReadingFlow", "speed": 3})


def test_parse_param_rejects_bad_json():
    with pytest.raises(ValueError):
        parse_param("{not json")


def test_parse_param_rejects_out_of_range():
    with pytest.raises(ValueError):
        parse_param({"task": "DailyReadingFlow", "minutes": 0})


def test_parse_param_rejects_non_number():
    with pytest.raises(ValueError):
        parse_param({"task": "DailyReadingFlow", "minutes": "abc"})



def test_unreplaced_placeholder_uses_default():
    """MFA 未替换的占位符（如 ``{cover_image}``）按缺省处理，取字段默认值。"""
    spec, values = parse_param(
        {
            "task": "DailyAudiobookFlow",
            "minutes": "{minutes}",
            "cover_image": "{cover_image}",
            "book_title": "{book_title}",
        }
    )
    assert spec.key == "DailyAudiobookFlow"
    assert values["minutes"] == 35.0
    assert values["cover_image"] == ""
    assert values["book_title"] == "全职法师"


def test_placeholder_like_text_with_extra_chars_is_kept():
    _, values = parse_param({"task": "DailyReadingFlow", "book_title": "{宇智波}/火影"})
    assert values["book_title"] == "{宇智波}/火影"


# ------------------------------------------------------------------ TaskRunner


def test_book_title_with_slash_passed_verbatim(tmp_path):
    spec, values = reading(book_title="宇智波 / 全职法师")
    runner, popen, _, _ = make_runner(
        tmp_path, [FakeProcess(101, 0), FakeProcess(102, 0)]
    )
    runner.run(spec, values)
    task_command = list(popen.calls[1])
    assert task_command[task_command.index("--book-title") + 1] == "宇智波 / 全职法师"
    assert "--task" in task_command
    assert task_command[task_command.index("--task") + 1] == "DailyReadingFlow"


def test_handoff_command_precedes_task(tmp_path):
    spec, values = reading()
    runner, popen, _, _ = make_runner(
        tmp_path, [FakeProcess(101, 0), FakeProcess(102, 0)]
    )
    runner.run(spec, values)
    handoff = list(popen.calls[0])
    assert handoff[handoff.index("--task") + 1] == "HandoffCheck"
    assert handoff[handoff.index("--next-task") + 1] == "DailyReadingFlow"
    env = popen.kwargs[1]["env"]
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert str(REPO_ROOT) in env["PYTHONPATH"].split(";") + env["PYTHONPATH"].split(":")


def test_success_requires_exit_zero(tmp_path):
    spec, values = reading()
    runner, _, _, _ = make_runner(tmp_path, [FakeProcess(101, 0), FakeProcess(102, 0)])
    ok = runner.run(spec, values)
    assert isinstance(ok, RunResult)
    assert ok.success is True
    assert ok.exit_code == 0

    runner, _, _, _ = make_runner(tmp_path, [FakeProcess(103, 0), FakeProcess(104, 2)])
    failed = runner.run(spec, values)
    assert failed.success is False
    assert failed.exit_code == 2
    assert "任务未成功" in failed.message


def test_captcha_handoff_does_not_start_task(tmp_path):
    spec, values = reading()
    runner, popen, _, _ = make_runner(tmp_path, [FakeProcess(101, 10), FakeProcess(102, 0)])
    result = runner.run(spec, values)
    assert len(popen.calls) == 1
    assert result.success is False
    assert result.exit_code == 10
    assert "BLOCKED_BY_CAPTCHA" in result.message


def test_task_captcha_exit_reports_blocked(tmp_path):
    spec, values = reading()
    runner, _, _, _ = make_runner(tmp_path, [FakeProcess(101, 0), FakeProcess(102, 10)])
    result = runner.run(spec, values)
    assert result.exit_code == 10
    assert "BLOCKED_BY_CAPTCHA" in result.message


def test_unsafe_handoff_skips_task(tmp_path):
    spec, values = reading()
    runner, popen, _, _ = make_runner(tmp_path, [FakeProcess(101, 20), FakeProcess(102, 0)])
    result = runner.run(spec, values)
    assert len(popen.calls) == 1
    assert result.success is False
    assert result.exit_code == 20


def _stop_from_second_poll():
    calls = {"n": 0}

    def is_stopping() -> bool:
        calls["n"] += 1
        return calls["n"] >= 2

    return is_stopping


def test_stop_during_handoff_kills_only_that_pid(tmp_path):
    spec, values = reading()
    handoff = FakeProcess(201, None)
    task = FakeProcess(202, 0)
    runner, popen, kill, _ = make_runner(
        tmp_path, [handoff, task], is_stopping=_stop_from_second_poll()
    )
    result = runner.run(spec, values)
    assert kill.pids == [201]
    assert len(popen.calls) == 1
    assert result.success is False
    assert result.exit_code == 13
    record = json.loads(result.record_path.read_text(encoding="utf-8"))
    assert record["state"] == "CANCELLED"


def test_stop_during_task_kills_task_pid(tmp_path):
    spec, values = reading()
    handoff = FakeProcess(301, 0)
    task = FakeProcess(302, None)
    calls = {"n": 0}

    def is_stopping() -> bool:
        # 交接阶段一直为假；任务进程启动后第二次轮询起为真。
        calls["n"] += 1
        return len(popen.calls) >= 2 and calls["n"] >= 4

    runner, popen, kill, _ = make_runner(tmp_path, [handoff, task], is_stopping=is_stopping)
    result = runner.run(spec, values)
    assert kill.pids == [302]
    assert len(popen.calls) == 2
    assert result.exit_code == 13
    record = json.loads(result.record_path.read_text(encoding="utf-8"))
    assert record["steps"][0]["state"] == "CANCELLED"


def test_missing_config_returns_failure(tmp_path):
    spec, values = reading()
    runner, popen, _, _ = make_runner(
        tmp_path, [], config_path=tmp_path / "missing.local.json"
    )
    result = runner.run(spec, values)
    assert result.success is False
    assert result.exit_code == 3
    assert "启动QQReaderGUI.cmd" in result.message
    assert popen.calls == []


def test_non_utf8_output_is_forwarded(tmp_path):
    spec, values = reading()
    runner, _, _, logs = make_runner(
        tmp_path,
        [FakeProcess(101, 0), FakeProcess(102, 0, [b"\xff ok\n", "中文行\n".encode("utf-8")])],
    )
    result = runner.run(spec, values)
    assert result.success is True
    assert any("ok" in line for line in logs)
    assert any("中文行" in line for line in logs)


def test_record_written(tmp_path):
    spec, values = reading()
    runner, _, _, _ = make_runner(tmp_path, [FakeProcess(101, 0), FakeProcess(102, 0)])
    result = runner.run(spec, values)
    assert result.record_path is not None and result.record_path.is_file()
    record = json.loads(result.record_path.read_text(encoding="utf-8"))
    assert record["run_id"].startswith("mfa_")
    assert record["steps"][0]["state"].lower() == "succeeded"
    assert record["steps"][0]["handoff"]["exit_code"] == 0


def test_module_does_not_import_maa():
    code = (
        "import sys, qqreader.mfa.agent_action; "
        "print(any(m == 'maa' or m.startswith('maa.') for m in sys.modules))"
    )
    output = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert output == "False"
