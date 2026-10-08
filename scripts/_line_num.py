"""ResolveManagerPath 全文看 30 行。"""
import subprocess

r = subprocess.run(
    ["cmd", "/c", r'powershell -NoProfile -Command "Select-String -Path \'D:\游戏文件\chatgpt\gameflow\src\Gameflow.Infrastructure.Windows\MuMuTargetAdapter.cs\' -Pattern \'ResolveManagerPath\' | Select-Object -First 1 | ForEach-Object { $_.LineNumber }"'],
    capture_output=True, text=True, timeout=30)
print(r.stdout, r.stderr[:200])
