"""根因明确（两个独立 bug）：
①live_captcha_auto.py 的 snap()：data 是裸像素 bytes（非 PNG）→
  write_bytes 存的 png 其实是坏文件 → detect_slide 解码失败。
  （之前两次成功是旧链路 save 正常 png。）
②detect_slide 本身：track/slider 都找到了，但「未检测到滑块缺口位置」——
  当前这个验证码变体的缺口检测算法失效（_find_gap_x 没匹配上）。

修复方案（不动 slide.py 的视觉算法，绕过）：
用 PNG 正确落盘 + 手动视觉核对缺口位置：把截图发给我看（MEDIA 发飞书），
人工确认缺口 x 坐标 → sendevent 滑动。同时提 issue 给 Codex 修①②。
先截屏发飞书人工判缺口。"""
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
out = Path(r"G:\project_X\runtime\screenshots\ad_watch\captcha_now.png")
s.save(str(out))
print("已保存:", out, out.stat().st_size)
client.close()
