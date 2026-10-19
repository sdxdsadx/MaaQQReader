"""终判: 用拼图缺口双向验证——比较缺口邻域与拼图头原始位置的纹理匹配。

更可靠: 找拼图块（有白色高亮的方块）在拼图区的精确位置。
用模板匹配: 以缺口峰 x=374 为目标，在拼图区 y=600..806 搜索「带白边的方形块」。
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

# 验证码结构（QQ阅读/uniapp 标准）:
#   - 拼图头（方块）通常与滑块按钮同步: 按钮中心 x=168 → 拼图头中心 x≈168
#   - 缺口中心 x=374 → 需要按钮位移 = 374-168 = 206px —— 恰好等于检测值！
# 那为什么失败？两种可能:
#   A. 滑动后页面校验的是「拼图头 vs 缺口」的像素对齐，但 MAA swipe 没拖住拼图头
#      （起点 y=818 在轨道上，但拼图头可能要求按在拼图块上 y≈600-800）
#   B. 行为检测（速度/轨迹），拟人化不足
# 判别: r2 的 CAPTCHA_DETECTED 截图（滑动前）与 BLOCKED（滑动后）对比拼图头位置
before = cv2.imdecode(np.frombuffer(Path(r"G:\project_X\runtime\screenshots\19700104\DailyAdFlow_19700104_042439_843000_003_CAPTCHA_DETECTED.png").read_bytes(), np.uint8), cv2.IMREAD_COLOR)
after = cv2.imdecode(np.frombuffer(Path(r"G:\project_X\runtime\screenshots\19700104\DailyAdFlow_19700104_041939_562000_013_BLOCKED_BY_CAPTCHA.png").read_bytes(), np.uint8), cv2.IMREAD_COLOR)

# 拼图区 y600..800 的横向边缘对比（拼图头是否移动了）
for name, im in (("滑动前", before), ("滑动后", after)):
    g = cv2.cvtColor(im[600:800, :], cv2.COLOR_BGR2GRAY)
    e = cv2.Canny(g, 50, 150)
    col = e.sum(axis=0) / e.shape[0]
    sm = np.convolve(col, np.ones(9) / 9, mode="same")
    top = int(np.argmax(sm))
    print(f"{name}: 最强竖边缘 x={top} (density={sm[top]:.1f})")

# 差分: 滑动前 vs 滑动后 在拼图区的绝对差（拼图头位移量）
g1 = cv2.cvtColor(before[600:800, :], cv2.COLOR_BGR2GRAY).astype(int)
g2 = cv2.cvtColor(after[600:800, :], cv2.COLOR_BGR2GRAY).astype(int)
diff = np.abs(g1 - g2).sum(axis=0)
# 找差分最大的连续区（拼图头从哪移到哪）
nz = np.where(diff > diff.max() * 0.3)[0]
if nz.size:
    print(f"差分集中区: x={nz.min()}..{nz.max()}（拼图头活动范围）")
