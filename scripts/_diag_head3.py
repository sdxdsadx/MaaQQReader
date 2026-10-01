"""J: 用放大图肉眼定位 + 色彩聚类。先看 _zoom_puzzle.png 放大图（人工），
同时输出容器带的调色板主色分布，找「拼图头」的颜色特征。
另外输出容器带缩略 ASCII 亮度图帮助定位。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

ACC = _ROOT / "runtime/screenshots/19700104"

img = cv2.imdecode(np.fromfile(str(ACC / "probeF_end.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
band = img[690:812, 60:655]
g = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)

# ASCII 亮度图（每 6px 采样一列、每 8px 一行）
chars = " .:-=+*#%@"
print("容器带亮度 ASCII（x: 60..655 每6px, y: 690..812 每8px）:")
for yy in range(0, band.shape[0], 8):
    row = ""
    for xx in range(0, band.shape[1], 6):
        v = g[yy:yy+8, xx:xx+6].mean()
        row += chars[min(9, int(v / 26))]
    print(f"{690+yy:4d} {row}")

# 列亮度均值曲线峰谷（拼图头=亮块或暗块？）
colmean = g.mean(axis=0)
print("\n列均值极值:")
print("  最亮 5 列 x_abs:", [(60 + int(i), int(colmean[i])) for i in np.argsort(colmean)[-5:]])
print("  最暗 5 列 x_abs:", [(60 + int(i), int(colmean[i])) for i in np.argsort(colmean)[:5]])
