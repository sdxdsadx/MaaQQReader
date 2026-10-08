"""codex 配置里无 astra 线索。astra 可能是 opencode/zcode/claude-code 的
模型名（用户多工具并用）。全工具扫描 model 列表里含 astra 的。"""
import subprocess

for tool, args in (("opencode", ["opencode", "models"]),
                   ("zcode", ["zcode", "models"]),
                   ("claude-code", None)):
    if args is None:
        continue
    try:
        r = subprocess.run(["cmd", "/c"] + args, capture_output=True, text=True,
                           timeout=40, errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        hits = [l.strip() for l in out.splitlines() if "astra" in l.lower()]
        print(f"{tool}: {'命中 ' + str(hits[:3]) if hits else '无'}")
    except Exception as e:
        print(f"{tool}: 探测失败 {e}")
