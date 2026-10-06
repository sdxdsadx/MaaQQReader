"""MFAAvalonia 的 Python Agent 入口（MaaFw 5.12.3）。

MFAAvalonia 按 ``mfa/interface.json`` 的 ``agent`` 段以 ``python -X utf8 ./agent/main.py
<socket_id>`` 启动本脚本（工作目录为 ``mfa/``）。本脚本只负责与 MaaFramework 对接：
注册自定义动作 ``QQReaderRunTask``，把参数交给 ``qqreader.mfa.agent_action`` 的纯逻辑。

``maa`` 只在 ``check_runtime()`` 通过之后才导入，这样单元测试（没有安装 MaaFw）
也能按路径加载本模块并测试 ``check_runtime``。
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import sys
from pathlib import Path
from typing import Optional

MFA_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_MAAFW_VERSION = "5.12.3"
_FIX_COMMAND = f'python -m pip install "MaaFw=={REQUIRED_MAAFW_VERSION}"'

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def check_runtime() -> Optional[str]:
    """检查 MaaFw 是否可用且版本正确；有问题时返回中文错误消息（含修复命令）。"""
    if importlib.util.find_spec("maa") is None:
        return (
            f"[QQReader Agent] 未安装 MaaFw（需要 {REQUIRED_MAAFW_VERSION}，与 MFAAvalonia v2.16.2 "
            f"内置的 MaaFramework 一致）。请运行：{_FIX_COMMAND}"
        )
    try:
        version = importlib.metadata.version("MaaFw")
    except importlib.metadata.PackageNotFoundError:
        version = None
    if version != REQUIRED_MAAFW_VERSION:
        return (
            f"[QQReader Agent] MaaFw 版本为 {version or '未知'}，需要 {REQUIRED_MAAFW_VERSION}"
            f"（必须与 MFAAvalonia 内置的 MaaFramework 一致）。请运行：{_FIX_COMMAND}"
        )
    return None


def _log(message: str) -> None:
    print(message, flush=True)


def main() -> None:
    error = check_runtime()
    if error:
        _log(error)
        sys.exit(2)

    from maa.agent.agent_server import AgentServer
    from maa.context import Context
    from maa.custom_action import CustomAction
    from maa.toolkit import Toolkit

    from qqreader.mfa.agent_action import (
        ACTION_NAME,
        DEFAULT_CONFIG_RELATIVE,
        TaskRunner,
        parse_param,
    )
    from qqreader.runner.exit_codes import EXIT_BLOCKED_BY_CAPTCHA

    @AgentServer.custom_action(ACTION_NAME)
    class QQReaderRunTask(CustomAction):
        def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
            try:
                spec, values = parse_param(argv.custom_action_param)
            except ValueError as exc:
                _log(f"[QQReader] 动作参数无效：{exc}")
                return CustomAction.RunResult(success=False)
            runner = TaskRunner(
                REPO_ROOT,
                REPO_ROOT / DEFAULT_CONFIG_RELATIVE,
                log=_log,
                is_stopping=lambda: bool(context.tasker.stopping),
            )
            result = runner.run(spec, values)
            if result.exit_code == EXIT_BLOCKED_BY_CAPTCHA:
                # 验证码：不继续后面的任务，停掉整个队列，等待人工处理。
                _log("[QQReader] BLOCKED_BY_CAPTCHA：停止 MFA 任务队列，等待人工处理验证码")
                context.tasker.post_stop()
            return CustomAction.RunResult(success=result.success)

    Toolkit.init_option(str(MFA_DIR))

    if len(sys.argv) < 2:
        _log("Usage: python main.py <socket_id>")
        _log("socket_id 由 MFAAvalonia 启动 Agent 时提供。")
        sys.exit(1)

    AgentServer.start_up(sys.argv[-1])
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
