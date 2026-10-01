"""派 codex 跑 MaaQQReader issue #2/#9/#1（默认模型 gpt-5.6-sol）。
ps5.1 引号坑绕过：python subprocess 列表参数。"""
import os
import shutil
import subprocess
from pathlib import Path

codex = shutil.which("codex")
env = os.environ.copy()
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
env["HTTP_PROXY"] = "http://127.0.0.1:7890"

prompt = ("读取 G:\\project_X\\.hermes\\issue2_task.md 并严格按其中任务执行"
          "（三个 issue：#2 修复、#9 验证后关闭、#1 查证处理），"
          "不要询问，全部完成后输出总结报告。")
r = subprocess.run(
    [codex, "exec", "--skip-git-repo-check", "--sandbox", "danger-full-access", prompt],
    cwd=r"G:\project_X", capture_output=True, text=True, timeout=550,
    errors="replace", env=env)
out = (r.stdout or "") + (r.stderr or "")
Path(r"G:\project_X\runtime\logs\codex_issue2_batch.log").write_text(out, encoding="utf-8")
print(f"exit={r.returncode}")
print(out[-800:])
