"""抓每个失败用例的详细错误（FAIL 块 + 后续 8 行）。"""
import re

log = open(r"G:\project_X\runtime\logs\gf_test16.log", encoding="utf-8", errors="replace").read()
# 找错误消息段
pat = re.compile(r"错误消息:\s*\r?\n\s*([^\r\n]+)")
msgs = pat.findall(log)
seen = set()
for m in msgs:
    key = m[:80]
    if key not in seen:
        seen.add(key)
        print("*", m[:160])
