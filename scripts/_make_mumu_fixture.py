"""Codex 没落地 TestData fixture（它只写了测试没拷数据）。补齐：
从真实探测输出生成 UTF-8 JSON fixture + csproj 加 CopyToOutputDirectory。"""
import json
import subprocess
from pathlib import Path

# 真实样本（UTF-16LE）转 UTF-8
src = Path(r"G:\project_X\runtime\logs\mumu_info_probe.txt")
raw = src.read_bytes()
text = raw.decode("utf-16-le", errors="ignore") if raw[:2] in (b"\xff\xfe",) else None
if text is None:
    # 从 PS 重定向产物里提取 JSON（找第一个 { 到最后一个 }）
    text = raw.decode("utf-8", errors="ignore")
start, end = text.find("{"), text.rfind("}")
payload = json.loads(text[start:end + 1])
# 保留结构，加一个已启动实例样例字段注释不可行(JSON)，直接输出规范 JSON
dst_dir = Path(r"D:\游戏文件\chatgpt\gameflow\tests\Gameflow.Infrastructure.Windows.Tests\TestData")
dst_dir.mkdir(parents=True, exist_ok=True)
(dst_dir / "mumu_info_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print("fixture 写入:", dst_dir / "mumu_info_probe.json")
print("实例数:", len(payload))
