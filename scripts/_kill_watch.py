"""看护循环陷入「toast 开启成功但页面永不翻页」死循环（卡第39章 2 小时+）。
自动阅读对这本书（短章魔法书）无效——章尾等待。看护重开无用。
换书策略：停掉当前看护进程 → 换全职法师（长章 342/3385，昨天验证 30min
自动阅读成功的就是它）→ 重新进正文 → 重启看护。"""
import subprocess

r = subprocess.run(
    ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:list"],
    capture_output=True, text=True, timeout=20)
for b in r.stdout.split("\n\n"):
    if "_autoread300_watch" in b:
        for line in b.splitlines():
            if line.startswith("ProcessId="):
                pid = line.split("=")[1].strip()
                print("杀看护进程:", pid)
                subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                               capture_output=True, timeout=20)
