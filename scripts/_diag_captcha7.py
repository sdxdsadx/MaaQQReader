"""终判 2: 滑动后拼图头 x=638（差分+边缘）——缺口 374。
拼图头: 前 197 → 后 638 = 位移 441px?! 按钮只滑了 206px。
比率: 441/206 ≈ 2.14 —— 轨道到拼图区的坐标缩放！
QQ阅读这类 uniapp 弹窗: 滑块轨道宽度 414px，拼图区显示宽度可能只有 ~193px
(轨道半宽)，拼图头移动 = 按钮位移 × (拼图区宽/轨道宽)。
反推: 缺口 374 需要拼图头从 197 移到 374 = 177px 拼图位移
→ 按钮应滑 177/2.14 ≈ 83px！而不是 206px。

验证: 若按 206 滑，拼图头应到 197+206×2.14=638 —— 与实测 638 完全吻合！！
（r2 的匀速滑动同样是 206px → 拼图头同样超到 638 → 拒绝）

结论：需要按 缩放系数 修正滑动距离: swipe_px = (缺口x - 拼图头x) / scale。
scale = 轨道可视宽/拼图区显示宽，需实测。本例 scale≈2.14（约等于
轨道宽414/拼图区宽193）。
"""
from pathlib import Path

import cv2
import numpy as np

after = cv2.imdecode(np.frombuffer(Path(r"G:\project_X\runtime\screenshots\19700104\DailyAdFlow_19700104_041939_562000_013_BLOCKED_BY_CAPTCHA.png").read_bytes(), np.uint8), cv2.IMREAD_COLOR)
gray = cv2.cvtColor(after[600:800, :], cv2.COLOR_BGR2GRAY)
e = cv2.Canny(gray, 50, 150)
col = e.sum(axis=0) / e.shape[0]
sm = np.convolve(col, np.ones(9) / 9, mode="same")
top = int(np.argmax(sm))
print(f"滑动后拼图头 x={top}")
puzzle_head_before = 197
gap_x = 374
scale = (638 - puzzle_head_before) / 206.0
corrected = (gap_x - puzzle_head_before) / scale
print(f"scale = 441/206 = {scale:.3f}")
print(f"正确滑动距离 = ({gap_x} - {puzzle_head_before}) / {scale:.3f} = {corrected:.0f}px")
print(f"（原检测 206px 滑过头 {206 - corrected:.0f}px → 拒绝合理）")
