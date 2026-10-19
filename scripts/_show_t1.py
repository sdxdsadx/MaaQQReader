"""剩 7 个，逐个看测试源码定修法。"""
from pathlib import Path

base = Path(r"D:\游戏文件\chatgpt\gameflow\tests\Gameflow.Infrastructure.Windows.Tests")

# 1) ResolveManagerPathExplainsProbedLocationsWhenMissing
t = (base / "MuMuInstanceDiscoveryTests.cs").read_text(encoding="utf-8")
i = t.find("ResolveManagerPathExplainsProbedLocationsWhenMissing")
print("== ResolveManager test ==")
print(t[i:i+520])
print()
# 2) ParseMuMuKeepsConfiguredValuesAndRejectsBadIndex
j = t.find("ParseMuMuKeepsConfiguredValuesAndRejectsBadIndex")
print("== ParseMuMuKeeps ==")
print(t[j:j+700])
