"""``python -m qqreader.config show|check --config <path>``。

用于验收「新仓库能启动并读取配置」「缺失必需配置时给出清晰提示」。
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from .errors import ConfigError
from .loader import load_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m qqreader.config",
        description="读取并校验 QQReader 配置（UTF-8 JSON/YAML）",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("show", "读取配置并打印解析结果"),
        ("check", "校验配置是否可读取"),
    ):
        child = sub.add_parser(command, help=help_text)
        child.add_argument("--config", required=True, help="配置文件路径（.json/.yaml/.yml）")
        child.add_argument(
            "--strict",
            action="store_true",
            help="额外检查 adb/模拟器/解释器路径是否存在",
        )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"[配置错误] {exc}", file=sys.stderr)
        return 2

    if args.command == "show":
        print(config.describe())
    else:
        print(f"[ok] 配置读取成功: {config.source}")

    if args.strict:
        missing = config.machine.missing_paths()
        if missing:
            print(
                "[配置错误] 以下路径不存在: " + ", ".join(str(path) for path in missing),
                file=sys.stderr,
            )
            return 2
        print("[ok] 严格检查通过：adb / 模拟器 / 解释器路径均存在")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
