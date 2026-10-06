"""由任务目录生成 ``mfa/interface.json`` 与 ``mfa/resource/pipeline/qqreader.json``。

用法：
    py -3.10 scripts/build_mfa_interface.py          # 写出两个文件
    py -3.10 scripts/build_mfa_interface.py --check  # 只比对，不一致时退出码 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.mfa.interface import (  # noqa: E402
    build_interface,
    build_pipeline,
    read_project_version,
)

INTERFACE_RELATIVE = Path("mfa/interface.json")
PIPELINE_RELATIVE = Path("mfa/resource/pipeline/qqreader.json")


def render(data: Any) -> str:
    return json.dumps(data, indent=4, ensure_ascii=False) + "\n"


def expected_files(root: Path = _ROOT) -> Dict[Path, str]:
    version = read_project_version(root / "pyproject.toml")
    return {
        INTERFACE_RELATIVE: render(build_interface(version=version)),
        PIPELINE_RELATIVE: render(build_pipeline()),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="只比对入库文件，不写入")
    args = parser.parse_args(argv)

    stale = []
    for relative, text in expected_files().items():
        path = _ROOT / relative
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == text:
            continue
        if args.check:
            stale.append(relative.as_posix())
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"已写入 {relative.as_posix()}")
    if stale:
        print("以下文件与任务目录不一致，请运行 py -3.10 scripts/build_mfa_interface.py：")
        for name in stale:
            print(f"  {name}")
        return 1
    if args.check:
        print("MFA interface 与 pipeline 与任务目录一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
