"""v4 r1 终诊断: 看 HOME 状态定义（书城页为何不满足）+ confirmer。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
profiles = (ROOT / "qqreader" / "page" / "profiles.py").read_text(encoding="utf-8")

# HOME 定义段
m = re.search(r"state=PageState\.HOME,.*?min_matched=\d+", profiles, re.S)
print("=== HOME StateDefinition ===")
print(m.group(0)[:1800] if m else "not found")
