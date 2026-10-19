"""2 个失败都是 game 相关（Codex 正在改 game.py，跟我 ad.py 的 GAME_HALL
改动无关？——test_qqr20 是「game_center 点首卡」，可能 Codex 已改了 game.py
和我的改动冲突？先看失败详情再定。"""
import subprocess

r = subprocess.run(
    ["cmd", "/c", "set PYTHONPATH=G:\\project_X&& D:\\python\\python.exe -m pytest tests/test_game_adapter_timer.py::test_game_flow_end_to_end_with_real_adapter -q --tb=short"],
    cwd=r"G:\project_X", capture_output=True, text=True, timeout=280)
out = (r.stdout or "") + (r.stderr or "")
print(out[-2200:])
