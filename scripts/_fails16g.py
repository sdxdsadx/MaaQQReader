"""精确提取 11 个失败用例名（[FAIL] 行 = 用例名行，xUnit 前缀行）。"""
import re

log = open(r"G:\project_X\runtime\logs\gf_test16.log", encoding="utf-8", errors="replace").read()
names = re.findall(r"\[xUnit[^\]]+\]\s+(Gameflow[^\r\n]+)\[FAIL\]", log)
seen = []
for n in names:
    n = n.strip()
    if n not in seen:
        seen.append(n)
for n in seen:
    print(n[:160])
print("共", len(seen))
