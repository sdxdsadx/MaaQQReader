"""G: 精确缺口定位——不再用 detect_slide 的近似。直接视觉分析:
截图当前帧, 在拼图容器 (60,690,595,120) 内找「拼图缺口」——即背景图上
的洞。方法: 容器内每列与相邻列的差异突变（缺口边缘是竖直亮/暗线），
取「宽度≈按钮宽118px 的暗色矩形」的中心。

同时修正一个长期误判: '缺口' 可能就在轨道内(拼图块滑进轨道槽)，
OCR y=818 'ıI/lll' 就是滑块在轨道上的刻痕。拼图缺口是图块上的洞。
用滑动前(r2 CAPTCHA_DETECTED) 的图块区域做背景建模: 缺口=该区域中
与滑块头同形状的暗框。直接可视化输出中间图人工确认。
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

ACC = _ROOT / "runtime/screenshots/19700104"

img = cv2.imdecode(np.fromfile(str(ACC / "probeF_end.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
# 拼图容器 y 690..810, x 60..655
box = img[690:812, 60:655]
g = cv2.cvtColor(box, cv2.COLOR_BGR2GRAY)
print("拼图容器亮度统计:", g.min(), g.mean().round(1), g.max())

# 列梯度（找竖直边缘）
gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)).sum(axis=0)
sm = np.convolve(gx, np.ones(5) / 5, mode="same")
peaks = [(int(x), round(float(sm[x]), 0)) for x in range(2, len(sm) - 2)
         if sm[x] == max(sm[max(0, x - 20):x + 20]) and sm[x] > 200]
print("容器内竖直边缘峰（x_abs=60+x, 强度）:", [(60 + a, b) for a, b in peaks][:12])

# 行梯度（找水平边）
gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)).sum(axis=1)
print("水平边峰（y_abs=690+y）:", [(690 + int(y), round(float(gy[y]), 0)) for y in range(len(gy)) if gy[y] > gy.mean() * 2][:8])

# 保存放大图人工看
big = cv2.resize(box, (box.shape[1] * 2, box.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
cv2.imencode(".png", big)[1].tofile(str(ACC / "_zoom_puzzle.png"))
print("放大图已存:", ACC / "_zoom_puzzle.png")
