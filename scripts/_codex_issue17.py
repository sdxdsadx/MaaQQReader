"""派 codex（默认模型）修 issue #17：自动阅读书源白名单守门。
同时处理 Claude Code 模型重置请求：查 claude 配置现状（模型字段），
重置为默认（用户回来登录 Claude 账号后再确认）。"""
import os
import shutil
import subprocess
from pathlib import Path

codex = shutil.which("codex")
env = os.environ.copy()
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
env["HTTP_PROXY"] = "http://127.0.0.1:7890"

prompt = ("读取 G:\\project_X\\.hermes\\issue17_task.md 并严格按其中任务执行，"
          "不要询问，全部完成后输出总结报告。")
r = subprocess.run(
    [codex, "exec", "--skip-git-repo-check", "--sandbox", "danger-full-access", prompt],
    cwd=r"G:\project_X", capture_output=True, text=True, timeout=550,
    errors="replace", env=env)
out = (r.stdout or "") + (r.stderr or "")
Path(r"G:\project_X\runtime\logs\codex_issue17.log").write_text(out, encoding="utf-8")
print(f"exit={r.returncode}")
print(out[-700:])
