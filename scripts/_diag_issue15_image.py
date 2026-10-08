"""issue #15 临时诊断：fixture 图像内容分析（OCR + 蓝色/灰色区域）。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

PNG = _ROOT / "runtime" / "screenshots" / "ad_watch" / "captcha_now.png"
data = PNG.read_bytes()
img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
h, w = img.shape[:2]
print("shape:", img.shape)

# 蓝色滑块区域（与 slide.py 同参数）
blue = cv2.inRange(img, (180, 50, 0), (255, 220, 180))
n, labels, stats, _ = cv2.connectedComponentsWithStats(blue, connectivity=8)
print("blue components > 200px:")
for i in range(1, n):
    x, y, bw, bh, area = stats[i]
    if area > 200:
        print(f"  box=({x},{y},{bw},{bh}) area={area}")

# 灰色轨道行扫描（与 slide.py 同参数）
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
mask = (gray >= 180) & (gray <= 220)
print("gray rows with run > 0.4*w:")
for yy in range(0, h):
    row = mask[yy, :]
    best = 0
    run = 0
    for x in range(w):
        if row[x]:
            run += 1
            best = max(best, run)
        else:
            run = 0
    if best > w * 0.4:
        print(f"  y={yy} run={best}")

# OCR（如果装了项目识别链路就直接用脚本；这里只做像素分析）
# 保存中央裁剪供人工查看
crop = img[380:760, :]
cv2.imwrite(str(_ROOT / "runtime" / "screenshots" / "ad_watch" / "_diag_crop.png"), crop)
print("crop saved")
