"""Claude Code 模型重置：settings.json 的 model 字段从 deepseek-flash
改为删除（使用默认模型）。用户回来登录 Claude 账号后生效。
备份原配置后修改。"""
import json
import shutil
from pathlib import Path

p = Path.home() / ".claude" / "settings.json"
backup = p.with_suffix(".json.bak-deepseek")
shutil.copy(p, backup)
cfg = json.loads(p.read_text(encoding="utf-8"))
old_model = cfg.pop("model", None)
p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"备份: {backup}")
print(f"已移除 model 字段（原值: {old_model}）→ Claude Code 将使用登录账号的默认模型")
