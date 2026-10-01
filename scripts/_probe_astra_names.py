"""astra 被网关拒绝（ChatGPT 账户不支持）——之前 pong=True 是误判
（exit=1 里混了错误但输出里碰巧含 pong 字样？不深究）。
正确做法：astra 需要自定义 provider/网关。查 codex config 里有没有
model_providers 段或历史用过的其他网关模型名。"""
import os
import shutil
import subprocess

codex = shutil.which("codex")
env = os.environ.copy()
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"

# 尝试常见 astra 变体名
for model in ("gpt-5.1-codex-astra", "gpt-5.6-sol-astra", "codex-astra-latest"):
    r = subprocess.run(
        [codex, "exec", "--skip-git-repo-check", "-m", model,
         "回复一个词：pong"],
        cwd=r"G:\project_X", capture_output=True, text=True, timeout=90,
        errors="replace", env=env)
    out = (r.stdout or "") + (r.stderr or "")
    ok = ("pong" in out.lower()) and ("not supported" not in out)
    print(f"model={model}: exit={r.returncode} ok={ok}")
    if not ok:
        print("  err:", out[-180:].replace(chr(10), " | "))
    if ok:
        print("✅ 找到可用 astra 模型名")
        break
