"""已在正文页（第230章屋顶对话）。现在启动 300 分钟看护（跳过导航段，
直接从自动阅读开启开始）——复用 _autoread_300.py 但加 --skip-nav 参数。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import _autoread_300 as core  # noqa: E402
