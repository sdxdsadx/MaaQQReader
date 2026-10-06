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
    assert "chcp 65001" in text
    assert "-m qqreader.gui" in text


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
