"""兼容旧启动方式的 GUI 入口：``python gui/maa_qq_reader_gui.py``。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.gui.app import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
