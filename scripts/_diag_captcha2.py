"""分析真实验证码截图: OCR/色块定位滑块与缺口，验证 206px 是否正确。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

p = Path(r"G:\project_X\runtime\screenshots\19700104\DailyAdFlow_19700104_042439_843000_003_CAPTCHA_DETECTED.png")
image = cv2.imdecode(np.frombuffer(p.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
h, w = image.shape[:2]
print(f"size: {w}x{h}")

# 蓝色滑块（沿用仓库算法参数）
blue = cv2.inRange(image, (180, 50, 0), (255, 220, 180))
blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
contours, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print("蓝色轮廓（全部）:")
for c in contours:
    x, y, cw, ch = cv2.boundingRect(c)
    area = cv2.contourArea(c)
    if area < 100:
        continue
    print(f"  box=({x},{y},{cw},{ch}) area={area:.0f}")

gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
# 轨道附近区域行扫描: y 806-832 轨道带，找灰色长条
print("\n灰色长条(y=790~840, 灰度180-220)行分析:")
for yy in range(790, 841, 10):
    row = gray[yy, :]
    mask = (row >= 180) & (row <= 220)
    runs = []
    run = 0
    start = 0
    for x, v in enumerate(mask):
        if v:
            if run == 0:
                start = x
            run += 1
        else:
            if run > 50:
                runs.append((start, run))
            run = 0
    if run > 50:
        runs.append((start, run))
    print(f"  y={yy}: {runs[:4]}")
