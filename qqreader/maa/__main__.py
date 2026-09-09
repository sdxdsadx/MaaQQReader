"""``python -m qqreader.maa doctor``：MaaFramework 连接自检。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from ..config import ConfigError, load_config
from .doctor import run_doctor


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m qqreader.maa",
        description="MaaFramework 适配器自检（真机或离线静态截图）",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="连接并检查截图 / OCR / 点击")
    doctor.add_argument("--config", required=True, help="QQReader 配置文件（UTF-8 JSON/YAML）")
    doctor.add_argument(
        "--offline-image",
        action="append",
        default=[],
        help="用静态 PNG 代替真机截图（可重复；离线模式）",
    )
    doctor.add_argument(
        "--offline-dir", default=None, help="用目录下的 PNG 代替真机截图（离线模式）"
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"[配置错误] {exc}", file=sys.stderr)
        return 2

    images = []
    for raw in args.offline_image:
        path = Path(raw)
        if not path.is_file():
            print(f"[配置错误] 离线截图不存在: {path}", file=sys.stderr)
            return 2
        images.append(path.read_bytes())
    offline_dir = Path(args.offline_dir) if args.offline_dir else None
    if offline_dir is not None and not offline_dir.is_dir():
        print(f"[配置错误] 离线截图目录不存在: {offline_dir}", file=sys.stderr)
        return 2

    report = run_doctor(config, offline_images=images, offline_dir=offline_dir)
    print(report.render())
    return 0 if report.ok else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
