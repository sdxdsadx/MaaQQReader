"""逐个看 11 个失败用例的完整错误块（FAIL 行 + 后 12 行）。"""
import re

log = open(r"G:\project_X\runtime\logs\gf_test16.log", encoding="utf-8", errors="replace").read()
lines = log.splitlines()
for i, l in enumerate(lines):
    if "[FAIL]" in l and "xUnit" not in l:
        name = l.strip()
        # 找该用例的错误消息（往后 40 行内）
        for j in range(i + 1, min(i + 40, len(lines))):
            if "错误消息" in lines[j]:
                print("用例:", name[:120])
                print("  错误:", lines[j + 1].strip()[:150])
                print()
                break
