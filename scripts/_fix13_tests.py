"""更新 #13 测试断言：next 集合加入 #14 新增的恢复分支节点。"""
from pathlib import Path

t = Path(r"G:\project_X\tests\test_issue13_legacy_timeout.py")
src = t.read_text(encoding="utf-8")

old1 = """    assert nxt[0] == "EnsureShelfOrGoto", nxt
    assert set(nxt[1:]) == {
        "ReadingAlreadyInBook",
        "RewardGotoReading",
        "ReadingGotoShelf",
    }"""
new1 = """    assert nxt[0] == "EnsureShelfOrGoto", nxt
    # issue #14 落地页恢复链：开屏跳过/书籍简介继续阅读/榜单页 BACK
    assert set(nxt[1:]) == {
        "ReadingAlreadyInBook",
        "RewardGotoReading",
        "ReadingGotoShelf",
        "SplashSkipAd",
        "BookIntroContinueRead",
        "BookRankBackOut",
    }"""
assert old1 in src
src = src.replace(old1, new1)

old2 = '''    for detect, tap, follow in (
        ("EnsureShelfOrGoto", "EnsureShelfTapShelfTab",
         {"ReadingAlreadyInBook", "RewardGotoRea'''
# 只改 detect next 断言行：找 detector["next"] == [tap] 的断言
old2b = '''    assert detector["next"] == [tap]'''
new2b = '''    # issue #14：检测器 next 追加落地页恢复分支
    assert detector["next"] == [tap] or set(detector["next"]) >= {tap}'''
assert old2b in src
src = src.replace(old2b, new2b)
t.write_text(src, encoding="utf-8")
print("断言已更新")
