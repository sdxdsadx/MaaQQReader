"""maafw.log 尾部时间戳是 21:53（昨天）——但文件 mtime 是刚刚！
说明有新内容但过滤词没匹配上。直接看最后 6 行原始内容。"""
from pathlib import Path

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
for r in rows[-6:]:
    print(r[:170])
