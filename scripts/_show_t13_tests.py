"""2 个失败原因：#13 的旧测试断言入口链 next 只有原 3 候选，但 #14 修复
在书城检测器 next 里追加了新恢复分支（SplashSkipAd/BookIntroContinueRead/
BookRankBackOut）——语义演进了，更新 #13 测试断言以匹配新链（新分支是
#14 明确要求的落地页恢复能力）。"""
from pathlib import Path

t = Path(r"G:\project_X\tests\test_issue13_legacy_timeout.py")
src = t.read_text(encoding="utf-8")

# 找第一个断言上下文
i = src.find("test_reading_entry_chain_prefers_bookstore_adaptation")
print(src[i:i+900])
