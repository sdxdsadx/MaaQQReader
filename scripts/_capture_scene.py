"""截取当前模拟器屏幕，保存场景证据。"""
import subprocess
from pathlib import Path

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"
out = Path(r"G:\project_X\runtime\screenshots\issue_scene")
out.mkdir(parents=True, exist_ok=True)
p = out / "current_scene.png"
with open(p, "wb") as fh:
    r = subprocess.run([adb, "-s", dev, "exec-out", "screencap", "-p"],
                       stdout=fh, stderr=subprocess.PIPE, timeout=30)
print("size:", p.stat().st_size if p.exists() else 0)
