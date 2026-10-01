"""修复缩进：assert 行必须保持原 8 空格缩进（在 for 循环内）。"""
from pathlib import Path

t = Path(r"G:\project_X\tests\test_issue13_legacy_timeout.py")
src = t.read_text(encoding="utf-8")
old = """        # issue #14：检测器 next 追加落地页恢复分支
    assert detector["next"] == [tap] or set(detector["next"]) >= {tap}"""
new = """        # issue #14：检测器 next 追加落地页恢复分支（保持 tap 为首选）
        assert detector["next"][0] == tap"""
assert old in src
src = src.replace(old, new)
t.write_text(src, encoding="utf-8")
print("缩进已修复")
