"""所有 astra 变体都被 ChatGPT 账户拒绝。astra 可能是 GLM 网关的模型
（用户之前配过 glm-5.3-flash）。查 codex config.toml 全文找 model_providers，
或检查用户 HERMES_HOME 的 config.yaml 里的 provider 线索。"""
from pathlib import Path
import os

cfg = Path(os.environ["USERPROFILE"]) / ".codex" / "config.toml"
src = cfg.read_text(encoding="utf-8", errors="replace")
print("config.toml 行数:", len(src.splitlines()))
# 打印 model_providers 相关段
i = src.find("model_providers")
if i >= 0:
    print(src[i:i+800])
else:
    print("无 model_providers 段")
print("===astra 全文搜索===")
for ln, line in enumerate(src.splitlines(), 1):
    if "astra" in line.lower():
        print(f"L{ln}: {line[:120]}")
