"""最终定位: 拼图缺口分析——把 Canny 峰值与滑块几何结合，计算正确滑动距离。

轨道 (225,810,414,20)（灰色），滑块按钮 (109,789,118,59)（蓝色，中心168,818）。
缺口 = 拼图背景上的洞（在轨道上方的拼图区内），形状与滑块头一致。
Canny 峰值 x_abs=372-376 → 缺口左/中缘。滑块按钮中心 168 → 滑到 374 处位移=206px。
**206px 看起来是对的**！那问题不在距离。检查拼图头位置：滑块头 y=789-848 但
拼图区 y≈500-800 —— 说明这个验证码的滑块头不在轨道上，而在拼图区内浮动？
再验证: OCR y=818 'lll' 是轨道上的滑块刻痕；y=896 'C' 是另一个元素。
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
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 拼图块（凸出的小图）通常贴着缺口。找 y=700..806 之间的强边缘竖线（块左边）
edges = cv2.Canny(gray[600:806, 0:720], 50, 150)
col = edges.sum(axis=0) / edges.shape[0]
sm = np.convolve(col, np.ones(9) / 9, mode="same")
peaks = []
for i in range(2, len(sm) - 2):
    if sm[i] > 8 and sm[i] == max(sm[max(0, i-15):i+15]):
        peaks.append((i, round(float(sm[i]), 1)))
print("拼图区竖向边缘峰 (x, density):", peaks[:12])

# 滑块按钮（蓝色）在 y=789..848 —— 轨道在 y=810..832，滑块按钮中心 y=818 在轨道上 ✓
# 距离=374-168=206 ✓。那为何不过？→ 检查拼图头 x 位置（滑块拖动时拼图头跟着走，
# 拼图头初始 x 应≈滑块按钮 x=109..227 范围）
# 找拼图头: 在 y=500..800 范围找与滑块头宽度近似(≈118px)的矩形块左缘
_, th = cv2.threshold(gray[500:806, :], 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
cs, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print("拼图头候选（y500-806, 宽80-160）:")
for c in cs:
    x, y, cw, ch = cv2.boundingRect(c)
    if 80 <= cw <= 160 and 40 <= ch <= 140 and cv2.contourArea(c) > 2000:
        print(f"  box=({x},{y+500},{cw},{ch})")
