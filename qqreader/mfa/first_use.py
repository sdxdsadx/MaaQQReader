"""启动 MFAAvalonia 前，把「新手教程已完成」写进它的界面配置。

MFAAvalonia 启动时读 ``config/config.json`` 的 ``UI.HasCompletedFirstUseTutorial``，
不是 ``true`` 就弹新手教程，只有把教程走完才会自己写入。``mfa/config/`` 不入库，
每份新的 MFA 目录（重新解压、新 worktree、换机）都没有这个键，所以每次都会弹。

本模块不导入 ``maa``。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

TUTORIAL_KEY = "UI.HasCompletedFirstUseTutorial"
CONFIG_RELATIVE_PATH = Path("config") / "config.json"


def ensure_tutorial_completed(mfa_dir: Path) -> bool:
    """保证教程开关为 ``true``；改写了配置文件返回 ``True``。

    配置文件存在但读不懂（不是 JSON 对象）时不动它，返回 ``False``。
    """
    config_path = Path(mfa_dir) / CONFIG_RELATIVE_PATH
    data: dict = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return False
        if not isinstance(data, dict):
            return False
        if data.get(TUTORIAL_KEY) is True:
            return False
    data[TUTORIAL_KEY] = True
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_name(config_path.name + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, config_path)
    return True


def main(argv: Optional[Sequence[str]] = None) -> int:
    """``python -m qqreader.mfa.first_use <mfa 目录>``；任何情况都返回 0，不拦启动。"""
    args = list(sys.argv[1:] if argv is None else argv)
    mfa_dir = Path(args[0]) if args else Path(__file__).resolve().parents[2] / "mfa"
    try:
        changed = ensure_tutorial_completed(mfa_dir)
    except OSError as exc:
        print(f"[warn] 未能关闭 MFAAvalonia 新手教程: {exc}")
        return 0
    if changed:
        print("[env] 已关闭 MFAAvalonia 新手教程")
    return 0


if __name__ == "__main__":
    sys.exit(main())
