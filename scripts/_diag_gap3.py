"""修正阈值重测: 按钮/缺口检测（阈值放宽到 <170，且限定 x 范围）。"""
from pathlib import Path

import cv2
import numpy as np

ACC = Path(r"G:\project_X\runtime\screenshots\19700104")
img = cv2.imdecode(np.fromfile(str(ACC / "probeF_end.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 按钮: y 788..806, x 100..400, 暗于 170
band = g[788:806, 100:400]
mask = band < 170
cols = mask.mean(axis=0)  # 每列暗像素比例
xs = np.where(cols > 0.7)[0]
if xs.size:
    print(f"按钮暗列: x {100+xs.min()}..{100+xs.max()} 中心={100+(int(xs.min())+int(xs.max()))//2}")

# 缺口: y 700..770, x 350..655, 暗于 150
band2 = g[700:770, 350:655]
m2 = (band2 < 150).mean(axis=0)
xs2 = np.where(m2 > 0.6)[0]
if xs2.size:
    print(f"缺口暗列: x {350+xs2.min()}..{350+xs2.max()} 中心={350+(int(xs2.min())+int(xs2.max()))//2}")
else:
    # 放宽
    xs2 = np.where(m2 > 0.4)[0]
    print(f"缺口暗列(宽0.4): x {350+xs2.min()}..{350+xs2.max()} 中心={350+(int(xs2.min())+int(xs2.max()))//2}" if xs2.size else "无暗段")
