"""判读: 206px 距离是否正确 + 失败原因假设验证。

事实：
- 滑块按钮（蓝）中心 (168, 818)，轨道 (225,810,414,20)
- Canny 缺口峰 x≈372-376 → 目标 374，距离 374-168=206 ✓ 几何自洽
- r2 两次滑动 206px 匀速被拒；r3 两次 206px 拟人被拒，且提示「已更换题目」

假设检验：滑块头（拼图块）初始 x 与按钮不同步。按钮 109..227 中心 168；
但拼图块左缘可能在 x≈140-197（竖边缘峰 140/197）。若拼图头左缘=197 而按钮
中心=168，拼图头中心≈197+59=256，要对齐缺口 374 → 需滑动 374-256=118px，
而非 206px！——按钮位移 ≠ 拼图头位移 的坐标换算问题。
再验证: r2 滑 206 后拼图头到 256+206=462，远超缺口 374（过冲 88px）→ 拒绝合理。
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

p = Path(r"G:\project_X\runtime\screenshots\19700104\DailyAdFlow_19700104_042439_843000_003_CAPTCHA_DETECTED.png")
img = cv2.imdecode(np.frombuffer(p.read_bytes(), np.uint8), cv2.IMREAD_COLOR)

# 直接裁出拼图头区域人工看: y 700..806（轨道上方），x 80..350
crop = img[690:810, 80:360]
out = Path(r"G:\project_X\runtime\screenshots\_diag_puzzle_head.png")
out.write_bytes(cv2.imencode(".png", crop)[1].tobytes())
print("裁剪保存:", out)

# 精确找拼图头: 它是带白边框的方块。找白色边框矩形 (BGR 白 ≈ 240+)
white = cv2.inRange(img[690:810, :], (235, 235, 235), (255, 255, 255))
cs, _ = cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print("白色边框轮廓（y690-810 全宽）:")
for c in cs:
    x, y, cw, ch = cv2.boundingRect(c)
    if cv2.contourArea(c) > 500 or (cw > 40 and ch > 30):
        print(f"  box_abs=({x},{y+690},{cw},{ch}) area={cv2.contourArea(c):.0f}")
