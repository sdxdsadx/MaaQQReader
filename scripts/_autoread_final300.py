"""300 分钟自动阅读（薄封装）。

实现已统一到 `scripts/auto_read_30min.py`（按老版本 `_run_direct_reading`
的 dwell 计时 + 分段重新进书模型重构）。本文件只负责固定 300 分钟。

用法: py -3.10 scripts/_autoread_final300.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import auto_read_30min


def main() -> int:
    sys.argv = [sys.argv[0], "--minutes", "300"]
    return auto_read_30min.main()


if __name__ == "__main__":
    raise SystemExit(main())
