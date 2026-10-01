"""修 IndentationError：new2b 的断言改法把多行结构改坏了。看现场。"""
from pathlib import Path

t = Path(r"G:\project_X\tests\test_issue13_legacy_timeout.py")
src = t.read_text(encoding="utf-8")
i = src.find('assert detector["next"]')
print(src[i-400:i+400])
