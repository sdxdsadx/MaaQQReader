"""分析: 缺口定位验证——轨道 (225,810,414,20)，滑块 (109,789,118,59)。
缺口应在轨道带内 (y≈810-830)。检查轨道带左右的暗色块（拼图缺口阴影）。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

p = Path(r"G:\project_X\runtime\screenshots\19700104\DailyAdFlow_19700104_042439_843000_003_CAPTCHA_DETECTED.png")
image = cv2.imdecode(np.frombuffer(p.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# 轨道带 y=810..832, x=225..639。滑块右缘 = 109+118 = 227。缺口应在 227 之后。
# 拼图缺口特征：与轨道同色的框内有一块边缘明显的矩形（拼图轮廓）。
roi = gray[806:834, 230:640]
_, th = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print("轨道带内暗色轮廓（候选缺口）:")
cands = []
for c in contours:
    x, y, cw, ch = cv2.boundingRect(c)
    area = cv2.contourArea(c)
    if area < 100:
        continue
    print(f"  box_abs=({x+230},{y+806},{cw},{ch}) area={area:.0f}")
    cands.append((area, x + 230 + cw // 2))

# 上下拼图块区域（缺口在图块上，不在轨道上！）：y 600..806 拼图区域找明显边缘
print("\n拼图区(500..800) Canny 列密度峰值:")
roi2 = gray[500:800, 230:640]
edges = cv2.Canny(roi2, 50, 150)
col = edges.sum(axis=0) / edges.shape[0]
sm = np.convolve(col, np.ones(7) / 7, mode="same")
top = np.argsort(sm)[-5:][::-1]
for i in sorted(top):
    print(f"  x_abs={i+230} density={sm[i]:.2f}")
