"""MFAAvalonia Agent 入口 ``mfa/agent/main.py`` 与启动脚本、.gitignore 的约定。

测试环境没有安装 MaaFw：``main.py`` 只有在 ``check_runtime()`` 通过后才导入
``maa``，所以这里可以按路径加载模块并直接测试 ``check_runtime``。
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = REPO_ROOT / "mfa" / "agent" / "main.py"
LAUNCHER = REPO_ROOT / "启动QQReaderGUI.cmd"


def _load_main():
    spec = importlib.util.spec_from_file_location("qqreader_mfa_agent_main", MAIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_import_does_not_require_maa():
    module = _load_main()
    assert callable(module.check_runtime)
    assert module.REQUIRED_MAAFW_VERSION == "5.12.3"


def test_check_runtime_reports_missing_maa(monkeypatch):
    module = _load_main()
    real_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a, **k: None if name == "maa" else real_find_spec(name, *a, **k),
    )
    message = module.check_runtime()
    assert message is not None
    assert "MaaFw==5.12.3" in message


def test_check_runtime_reports_version_mismatch(monkeypatch):
    module = _load_main()
    real_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a, **k: object() if name == "maa" else real_find_spec(name, *a, **k),
    )
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "5.14.2")
    message = module.check_runtime()
    assert message is not None
    assert "5.14.2" in message
    assert "5.12.3" in message


def test_check_runtime_ok_when_version_matches(monkeypatch):
    module = _load_main()
    real_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a, **k: object() if name == "maa" else real_find_spec(name, *a, **k),
    )
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "5.12.3")
    assert module.check_runtime() is None


def test_launcher_has_classic_branch():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "classic" in text
    assert "MFAAvalonia.exe" in text
    assert "MaaFw==5.12.3" in text
    assert "chcp 65001" not in text
    assert "-m qqreader.gui" in text


def test_debug_launcher_gui_mode_uses_mfa_entrypoint():
    text = (REPO_ROOT / "调试QQReader.cmd").read_text(encoding="gbk")
    assert 'call "%ROOT%启动QQReaderGUI.cmd"' in text
    assert "ProcessName -eq 'MFAAvalonia'" in text
    assert '%PYEXE% -m qqreader.gui --config "%CONFIG%"' not in text


@pytest.mark.skipif(shutil.which("git") is None, reason="需要 git")
def test_gitignore_keeps_mfa_sources():
    def ignored(path: str) -> bool:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", path],
            cwd=str(REPO_ROOT),
            capture_output=True,
        )
        assert result.returncode in (0, 1), result.stderr
        return result.returncode == 0

    assert not ignored("mfa/interface.json")
    assert not ignored("mfa/agent/main.py")
    assert not ignored("mfa/resource/pipeline/qqreader.json")
    assert ignored("mfa/MFAAvalonia.exe")
    assert ignored("mfa/config/config.json")
    assert ignored("mfa/logs/gui.log")
    assert ignored("mfa/debug/maa.log")
    assert ignored("mfa/resource/mfa_layout.json")


# ------------------------------------------------------------------ 动作注册（伪造 maa 模块）


class _FakeRunResult:
    def __init__(self, success):
        self.success = success


class _FakeCustomAction:
    RunArg = object
    RunResult = _FakeRunResult


class _FakeTasker:
    def __init__(self):
        self.stopping = False
        self.post_stop_calls = 0

    def post_stop(self):
        self.post_stop_calls += 1


class _FakeContext:
    def __init__(self):
        self.tasker = _FakeTasker()


class _FakeArgv:
    custom_action_param = '{"task": "fake"}'


def _install_fake_maa(monkeypatch):
    """在 sys.modules 注入最小 ``maa`` 伪模块，返回已注册动作的字典。"""
    import sys
    import types

    registered = {}

    class FakeAgentServer:
        @staticmethod
        def custom_action(name):
            def decorator(cls):
                registered[name] = cls
                return cls

            return decorator

    modules = {
        "maa": types.ModuleType("maa"),
        "maa.agent": types.ModuleType("maa.agent"),
        "maa.agent.agent_server": types.ModuleType("maa.agent.agent_server"),
        "maa.context": types.ModuleType("maa.context"),
        "maa.custom_action": types.ModuleType("maa.custom_action"),
        "maa.toolkit": types.ModuleType("maa.toolkit"),
    }
    modules["maa.agent.agent_server"].AgentServer = FakeAgentServer
    modules["maa.context"].Context = object
    modules["maa.custom_action"].CustomAction = _FakeCustomAction
    modules["maa.toolkit"].Toolkit = object
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    return registered


def _register_with_runner(monkeypatch, runner_factory):
    from qqreader.mfa import agent_action

    registered = _install_fake_maa(monkeypatch)
    monkeypatch.setattr(agent_action, "parse_param", lambda raw: ("spec", {}))
    monkeypatch.setattr(agent_action, "TaskRunner", runner_factory)
    module = _load_main()
    module.register_actions()
    return registered[agent_action.ACTION_NAME]


def _runner_returning(exit_code):
    from qqreader.mfa.agent_action import RunResult

    class StubRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, spec, values):
            return RunResult(exit_code == 0, exit_code, "stub", None)

    return StubRunner


def test_captcha_exit_stops_whole_queue(monkeypatch):
    action_cls = _register_with_runner(monkeypatch, _runner_returning(10))
    context = _FakeContext()
    result = action_cls().run(context, _FakeArgv())
    assert context.tasker.post_stop_calls == 1
    assert result.success is False


def test_success_exit_does_not_stop_queue(monkeypatch):
    action_cls = _register_with_runner(monkeypatch, _runner_returning(0))
    context = _FakeContext()
    result = action_cls().run(context, _FakeArgv())
    assert context.tasker.post_stop_calls == 0
    assert result.success is True


def test_unexpected_exception_returns_failure(monkeypatch, capsys):
    class RaisingRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, spec, values):
            raise RuntimeError("boom")

    action_cls = _register_with_runner(monkeypatch, RaisingRunner)
    context = _FakeContext()
    result = action_cls().run(context, _FakeArgv())
    assert result.success is False
    assert context.tasker.post_stop_calls == 0
    out = capsys.readouterr().out
    assert "[QQReader] 动作异常" in out
    assert "RuntimeError: boom" in out
