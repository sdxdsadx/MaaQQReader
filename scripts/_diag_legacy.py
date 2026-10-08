"""读旧流程完整日志：maafw 子进程启动失败（child return error [argv...）。
看 run_maa_ad.py 怎么拼 argv / 找 framework。"""
from pathlib import Path

ROOT = Path(r"G:\project_X")
legacy_log = None
for cand in (ROOT / "runtime" / "logs", ROOT / "_backup_old_project_20260909_200716" / "logs"):
    if cand.is_dir():
        for f in cand.glob("*.log"):
            pass
# 直接看 run_maa_ad.py 的入口逻辑
src = (ROOT / "_backup_old_project_20260909_200716" / "tools" / "run_maa_ad.py").read_text(encoding="utf-8", errors="replace")
import re
# 找 framework/resource 相关行
for i, line in enumerate(src.splitlines(), 1):
    if re.search(r"framework|resource|maa|argv|Path\(", line) and not line.strip().startswith("#"):
        print(f"L{i}: {line.strip()[:130]}")
