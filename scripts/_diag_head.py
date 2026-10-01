"""H: 终极定位——拼图头与缺口的**模板匹配**。
拼图头（浮动的方块图块）有独特白色描边。用 r2 的 CAPTCHA_DETECTED 截图
（拼图头在起点 197 附近）裁出拼图头模板，然后在当前帧全图 matchTemplate
找拼图头现在在哪；再裁「缺口」——缺口是背景图上的洞（背景在缺口处被挖空
且有白色描边阴影），在拼图头路径的 y 带上找与模板最匹配的洞位。

先验证一个更简单的假设: 拼图头 y 坐标其实是 690..810（容器），不是 600..800!
head_x 一直测 600..800 带的边缘，测到的可能是背景内容边缘而非拼图头。
r2 按钮滑 206 拼图头若 1:1 从 197→403，而 403 附近 r2 图中有没有边缘峰？
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

ACC = _ROOT / "runtime/screenshots/19700104"

before = cv2.imdecode(np.fromfile(str(ACC / "DailyAdFlow_19700104_042439_843000_003_CAPTCHA_DETECTED.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
after = cv2.imdecode(np.fromfile(str(ACC / "DailyAdFlow_19700104_041939_562000_013_BLOCKED_BY_CAPTCHA.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
now = cv2.imdecode(np.fromfile(str(ACC / "probeF_end.png"), dtype=np.uint8), cv2.IMREAD_COLOR)

# 在 y 690..810（拼图容器带）测「拼图头」：滑动前应贴左（x≈197），r2 滑 206 后应在 403
for tag, im in (("r2前", before), ("r2后", after), ("现在", now)):
    band = cv2.cvtColor(im[690:810, 60:655], cv2.COLOR_BGR2GRAY)
    gx = np.abs(cv2.Sobel(band, cv2.CV_32F, 1, 0, ksize=3)).sum(axis=0)
    sm = np.convolve(gx, np.ones(5) / 5, mode="same")
    # 找 x=100..250 的峰（拼图头起始区）
    seg = sm[40:200]
    peak_head = 60 + int(np.argmax(seg)) + 40
    print(f"{tag}: 容器带左区(100..260)最强边 x={peak_head} 强度={float(sm[peak_head-60]):.0f}")
