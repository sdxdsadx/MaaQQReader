"""🎯 重大时刻：广告「奖励已发放」+ 回到奖励页 + **检测到滑动验证码**！
立即截图存证 → 调用 live_captcha_auto.py 求解 → 验证消失。
这正是用户要求的完整链路验证。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()

# 截图存证
s = client.screencap()
SHOT = Path(r"G:\project_X\runtime\screenshots\ad_watch")
SHOT.mkdir(parents=True, exist_ok=True)
img_path = SHOT / "captcha_scene_1.png"
# screencap 返回 Screenshot 对象——用 save 或 bytes 接口
try:
    img_path.write_bytes(bytes(s))
except Exception:
    try:
        s.save(str(img_path))
    except Exception as e:
        print("截图保存失败:", e, flush=True)
print("截图:", img_path, img_path.exists(), flush=True)
client.close()

# 调用验证码求解器
print(">>> 调用 live_captcha_auto.py <<<", flush=True)
r = subprocess.run(
    [r"D:\python\python.exe", r"G:\project_X\scripts\live_captcha_auto.py"],
    cwd=r"G:\project_X", capture_output=True, text=True, timeout=150, errors="replace")
print(r.stdout[-800:], flush=True)
if r.stderr:
    print("STDERR:", r.stderr[-300:], flush=True)
