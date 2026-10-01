"""GameFlow 无 open issue。用户要求：codex 多跑 GameFlow 任务、直接用
astra 模型、确保 5 小时额度用完。
策略：给 codex(astra) 派一批**自我探索式任务**——让它审查 GameFlow
代码库找改进点/缺陷并逐个修复（每轮一个主题，连续派发直到额度用完）。
先探测 astra 模型是否可用（之前 ChatGPT 账户拒绝过 astra，用户现在明确
要求用 astra——可能账户已切换或 astra 现已开放）。"""
import os
import shutil
import subprocess

codex = shutil.which("codex")
env = os.environ.copy()
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
env["HTTP_PROXY"] = "http://127.0.0.1:7890"

r = subprocess.run(
    [codex, "exec", "--skip-git-repo-check", "-m", "astra", "回复一个词：pong"],
    cwd=r"D:\游戏文件\chatgpt\gameflow", capture_output=True, text=True,
    timeout=90, errors="replace", env=env)
out = (r.stdout or "") + (r.stderr or "")
ok = "pong" in out.lower() and "not supported" not in out
print(f"astra 探测: exit={r.returncode} ok={ok}")
if not ok:
    print("err:", out[-250:].replace(chr(10), " | "))
