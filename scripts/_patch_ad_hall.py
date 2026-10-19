"""'精选大作'页=GAME_HALL（游戏大厅首页）。GAME_HALL 在 ad.py 有分支吗？
这是 #10 修过的收紧 GAME_HALL marker。广告任务遇 GAME_HALL 应该 BACK
（游戏大厅也不是奖励页）。把 GAME_HALL 也纳入兜底集合，一次到位：
None / GAME_CENTER / GAME_HALL 都 BACK。"""
from pathlib import Path

p = Path(r"G:\project_X\qqreader\tasks\ad.py")
src = p.read_text(encoding="utf-8")
old = """        if state is None or state is PageState.GAME_CENTER:"""
new = """        if state in (None, PageState.GAME_CENTER, PageState.GAME_HALL):"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("GAME_HALL 纳入兜底")
