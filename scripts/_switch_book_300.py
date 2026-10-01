"""⚠ 又出现「toast 已开启但页面不翻页」（第47章停 5 分钟+）。
昨天同样的书全职法师 auto_read 30 分钟是持续翻页的。差异排查：
昨天成功的书=全职法师（第342章长章），今天这本=斗罗大陆同人（第230章）。
可能这本书「自动阅读」功能被会员限制（非会员书不能用自动阅读？
页面提示过「会员本书免费听」）。
验证法：手动呼菜单看设置面板「自动阅读」状态——toast 已开启说明开关开了
但 app 没执行翻页 = 这本书不支持。
解法：换回全职法师（昨天验证 auto_read 成功的那本）跑 300 分钟。
动作：停当前看护 → BACK 回书架 → 全职法师 → 347章续读 → 重启看护脚本。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

# 停当前看护
r = subprocess.run(
    ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:list"],
    capture_output=True, text=True, timeout=20)
for b in r.stdout.split("\n\n"):
    if "_autoread_final300" in b:
        for line in b.splitlines():
            if line.startswith("ProcessId="):
                pid = line.split("=")[1].strip()
                subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                               capture_output=True, timeout=20)
                print("已停旧看护:", pid, flush=True)

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()

# BACK 回书架
subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
               capture_output=True, timeout=15)
time.sleep(2.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
qz = [(t, b) for t, b in boxes if "全职法师" in t]
prog = [(t, b) for t, b in boxes if "3385" in t or ("342章" in t)]
print("全职法师:", qz, "| 347章行:", prog, flush=True)
target = prog[0] if prog else (qz[0] if qz else None)
if target:
    t, b = target[1]
    client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:5])[:110], flush=True)
client.close()
print("换书完成，重启看护")
