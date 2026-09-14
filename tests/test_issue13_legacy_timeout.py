"""issue #13 回归测试：legacy 子进程挂死 + 书城页入口适配。

锁定行为：

* :func:`run_task._run_legacy_task` 在子进程 stdout 已输出最终结果 JSON 行
  （``{"success": ..., "status": ...}``）后，子进程若在宽限期内不退出，
  必须主动 terminate 并按 JSON 结果返回（不得无限死等 ``wait()``）；
* terminate 后仍不退出时，用 ``taskkill /PID <pid> /T /F`` 整树兜底；
* 没有最终 JSON 时保持原行为（无超时 ``wait()``，不 kill）；
* ``dev/resource/pipeline/qq_reader_trial.json`` 的 ``DirectReadingFlow`` /
  ``DailyAudiobookFlow`` 入口链首节点前置书城页适配（EnsureShelfOrGoto），
  且所有 ``next`` 引用的节点都存在。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import run_task  # noqa: E402 - scripts 是脚本目录而非包模块

PIPELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "dev" / "resource" / "pipeline" / "qq_reader_trial.json"
)


# --------------------------------------------------------------------- JSON 行解析


def test_parse_final_result_line_accepts_result_object() -> None:
    parsed = run_task._parse_final_result_line(
        '{"success": false, "status": 4000, "entry": "DirectReadingFlow"}\n'
    )
    assert parsed == {"success": False, "status": 4000, "entry": "DirectReadingFlow"}


def test_parse_final_result_line_rejects_plain_lines() -> None:
    assert run_task._parse_final_result_line("[legacy] ADB 预检: ok") is None
    assert run_task._parse_final_result_line("") is None
    # 必须带 success 字段才算最终结果行
    assert run_task._parse_final_result_line('{"status": 4000}') is None
    assert run_task._parse_final_result_line('{"success": "oops"') is None


# --------------------------------------------------------------------- 挂死回归


class _FakeStdout:
    """按脚本逐行吐出 stdout 内容（替代真实管道迭代）。"""

    def __init__(self, lines: List[str]) -> None:
        self._lines = list(lines)

    def __iter__(self):  # noqa: D105 - 模拟 text 模式管道
        return iter(self._lines)


class _HungAfterJsonProcess:
    """模拟 run_maa_ad.py：stdout 已给出最终 JSON，但进程挂死不退出。

    真实 wait 语义建模：

    * ``wait()``（无 timeout，无 JSON 路径）→ 返回自然退出码；
    * 宽限期 ``wait(timeout=30)`` → 挂死，抛 :class:`TimeoutExpired`；
    * terminate 之后的补偿 ``wait(timeout=10)`` → ``terminate_effective``
      为真时返回 0（terminate 有效），否则继续抛（terminate 无效 →
      走 taskkill 兜底）。
    """

    def __init__(
        self,
        stdout: _FakeStdout,
        *,
        terminate_effective: bool = True,
        exit_code: int = 5,
    ) -> None:
        self.stdout = stdout
        self.pid = 424242
        self.exit_code = exit_code
        self.terminate_effective = terminate_effective
        self.terminate_calls = 0
        self.wait_timeouts: List[Optional[float]] = []

    def wait(self, timeout: Optional[float] = None) -> int:
        self.wait_timeouts.append(timeout)
        if timeout is None:
            # 无 JSON 路径的原生 wait：子进程最终自然退出。
            return self.exit_code
        if self.terminate_calls == 0:
            # 宽限期 wait：挂死进程不退出。
            raise subprocess.TimeoutExpired(cmd="run_maa_ad", timeout=timeout)
        if self.terminate_effective:
            return 0
        raise subprocess.TimeoutExpired(cmd="run_maa_ad", timeout=timeout)

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:  # pragma: no cover - 修复路径不应走到
        raise AssertionError("不应调用 kill()（terminate/taskkill 才是修复语义）")


def _fake_config() -> SimpleNamespace:
    return SimpleNamespace(
        machine=SimpleNamespace(
            maa_resource_dir=str(PIPELINE_PATH.parent.parent),
            maa_runtime_dir="dev",
            adb_path="adb.exe",
            adb_address="127.0.0.1:16384",
            package_name="com.qq.reader",
            log_dir="runtime/logs",
        )
    )


def _patch_legacy_env(
    monkeypatch: pytest.MonkeyPatch,
    process: _HungAfterJsonProcess,
    *,
    grace_seconds: float = 1.0,
    on_subprocess_run: Optional[Callable[..., Any]] = None,
) -> None:
    """屏蔽外部副作用：Popen / taskkill / ADB 预检，缩短宽限期。"""
    monkeypatch.setattr(
        run_task, "LEGACY_FINAL_EXIT_GRACE_SECONDS", grace_seconds
    )
    monkeypatch.setattr(
        run_task.subprocess, "Popen", lambda command, **kwargs: process
    )
    if on_subprocess_run is not None:
        monkeypatch.setattr(run_task.subprocess, "run", on_subprocess_run)
    else:
        monkeypatch.setattr(
            run_task.subprocess, "run",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("不应走到 taskkill 兜底")
            ),
        )
    # 函数体内是局部 import ensure_maa_ready，必须 patch 源模块。
    monkeypatch.setattr(
        "qqreader.maa.adb.ensure_maa_ready", lambda *a, **k: (True, "fake adb ok")
    )


def test_legacy_hung_process_killed_after_final_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """stdout 已输出最终 JSON、子进程挂死 → 宽限期后 terminate，按 JSON 返回。"""
    process = _HungAfterJsonProcess(
        _FakeStdout([
            "[legacy] MAA post entry DirectReadingFlow\n",
            '{"success": false, "status": 4000, "entry": "DirectReadingFlow"}\n',
        ]),
    )
    _patch_legacy_env(monkeypatch, process)

    exit_code = run_task._run_legacy_task("DailyReadingFlow", _fake_config(), None)

    assert exit_code == 2, "success=false 的最终 JSON 应映射为退出码 2"
    assert process.terminate_calls == 1, "挂死子进程必须被主动 terminate"
    assert process.wait_timeouts[0] == 1.0, "JSON 后的 wait 必须带宽限期 timeout"
    out = capsys.readouterr().out
    assert "主动终止" in out, "应打印主动终止提示"
    assert '"status": 4000' in out, "最终 JSON 行应先透传到 stdout"


def test_legacy_success_json_maps_to_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """success=true 的最终 JSON + 挂死 → terminate 后返回 0（任务成功）。"""
    process = _HungAfterJsonProcess(
        _FakeStdout([
            '{"success": true, "status": 3000, "entry": "DailyAudiobookFlow"}\n',
        ]),
    )
    _patch_legacy_env(monkeypatch, process)

    exit_code = run_task._run_legacy_task("DailyAudiobookFlow", _fake_config(), None)

    assert exit_code == 0
    assert process.terminate_calls == 1
    assert "主动终止" in capsys.readouterr().out


def test_legacy_taskkill_fallback_when_terminate_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """terminate 后仍不退出 → taskkill /PID <pid> /T /F 整树兜底，仍按 JSON 返回。"""
    process = _HungAfterJsonProcess(
        _FakeStdout(['{"success": false, "status": 4000, "entry": "DirectReadingFlow"}\n']),
        terminate_effective=False,
    )
    run_calls: List[List[str]] = []

    def fake_subprocess_run(args, **kwargs):
        run_calls.append(list(args))
        return SimpleNamespace(returncode=0)

    _patch_legacy_env(
        monkeypatch, process, on_subprocess_run=fake_subprocess_run
    )

    exit_code = run_task._run_legacy_task("DailyReadingFlow", _fake_config(), None)

    assert exit_code == 2
    assert process.terminate_calls == 1
    assert run_calls, "terminate 无效时必须调用 taskkill 兜底"
    assert run_calls[0][:2] == ["taskkill", "/PID"]
    assert str(process.pid) in run_calls[0]
    assert "/T" in run_calls[0] and "/F" in run_calls[0]


def test_legacy_without_final_json_keeps_plain_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """没有最终 JSON 行时保持原行为：无超时 wait()、不 kill。"""
    process = _HungAfterJsonProcess(
        _FakeStdout(["[legacy] ADB 预检: ok\n", "[legacy] MAA running...\n"]),
        exit_code=5,
    )
    _patch_legacy_env(monkeypatch, process)

    exit_code = run_task._run_legacy_task("DailyReadingFlow", _fake_config(), None)

    assert exit_code == 5, "应透传子进程退出码"
    assert process.wait_timeouts == [None], "无 JSON 时不得引入超时"
    assert process.terminate_calls == 0


def test_legacy_grace_constant_is_30_seconds() -> None:
    assert run_task.LEGACY_FINAL_EXIT_GRACE_SECONDS == 30.0


# --------------------------------------------------------------------- 书城页入口适配


def _load_pipeline() -> Dict[str, Any]:
    return json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))


def test_reading_entry_chain_prefers_bookstore_adaptation() -> None:
    data = _load_pipeline()
    nxt = data["DirectReadingFlow"]["next"]
    assert nxt[0] == "EnsureShelfOrGoto", nxt
    assert set(nxt[1:]) == {
        "ReadingAlreadyInBook",
        "RewardGotoReading",
        "ReadingGotoShelf",
    }


def test_audiobook_entry_chain_prefers_bookstore_adaptation() -> None:
    data = _load_pipeline()
    nxt = data["DailyAudiobookFlow"]["next"]
    assert nxt[0] == "EnsureShelfOrGotoAudio", nxt
    assert set(nxt[1:]) == {
        "AudiobookPlaying",
        "AudiobookFindBook",
        "AudiobookOpenFirstShelfBook",
        "AudiobookBackUntilShelf",
    }


def test_bookstore_nodes_detect_and_click_shelf_tab() -> None:
    data = _load_pipeline()
    for detect, tap, follow in (
        ("EnsureShelfOrGoto", "EnsureShelfTapShelfTab",
         {"ReadingAlreadyInBook", "RewardGotoReading", "ReadingGotoShelf"}),
        ("EnsureShelfOrGotoAudio", "EnsureShelfTapShelfTabAudio",
         {"AudiobookPlaying", "AudiobookFindBook",
          "AudiobookOpenFirstShelfBook", "AudiobookBackUntilShelf"}),
    ):
        detector = data[detect]
        assert detector["recognition"] == "OCR"
        assert detector["expected"] == "排行榜|男生|免费"
        assert detector["action"] == "DoNothing"
        assert detector["next"] == [tap]
        tapper = data[tap]
        assert tapper["recognition"] == "OCR"
        assert tapper["expected"] == "^书架$"
        assert tapper["action"] == "Click"
        assert tapper["target"] == [70, 1250]
        assert tapper["post_delay"] == 2500
        assert set(tapper["next"]) == follow


def test_pipeline_next_references_all_resolve() -> None:
    """所有 next 引用的节点必须存在（issue #13 要求的完整性检查）。"""
    data = _load_pipeline()
    broken = []
    for name, node in data.items():
        if not isinstance(node, dict):
            continue
        for ref in node.get("next", []) or []:
            if ref not in data:
                broken.append(f"{name} -> {ref}")
        on_error = node.get("on_error")
        if isinstance(on_error, str) and on_error not in data:
            broken.append(f"{name} -> (on_error) {on_error}")
    assert not broken, broken
