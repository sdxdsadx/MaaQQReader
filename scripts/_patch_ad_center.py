"""真相：游戏中心页有独立 PageState.GAME_CENTER！
所以 ad.py advance 收到 GAME_CENTER（非 None），我的 UNKNOWN 兜底不触发；
而 ad.py 的分支只处理 HOME/REWARD_HOME/AD_*，GAME_CENTER 落到
super().advance() → 无动作空转。game.py 的 #12 修复由 Codex 做同样页面。

ad.py 最小修复：GAME_CENTER → press_back（广告任务不关心游戏中心）。
改 UNKNOWN 兜底为 state in (None, PageState.GAME_CENTER)。"""
from pathlib import Path

p = Path(r"G:\project_X\qqreader\tasks\ad.py")
src = p.read_text(encoding="utf-8")
old = """        if state is None:
            unknowns = int(context.get("ad_unknown_backs", 0))"""
new = """        if state is None or state is PageState.GAME_CENTER:
            unknowns = int(context.get("ad_unknown_backs", 0))"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("GAME_CENTER 纳入兜底")
