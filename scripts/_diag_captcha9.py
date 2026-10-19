"""r5 判读: raw=380? 滑 178 失败。380 是新题的缺口检测——但 380/2.14=178。
问题: raw 应该是「缺口x - 按钮中心x」。上一轮成功标定的真实关系:
  按钮位移 d_button → 拼图头位移 d_head = d_button × 2.14
  缺口在拼图区 x_gap（屏幕坐标），拼图头起点 head0（屏幕坐标）
  对齐条件: head0 + d_button×2.14 = x_gap → d_button = (x_gap - head0)/2.14
而检测器 raw = x_gap - button_center（按钮中心≈拼图头起点？）
r2 数据: 按钮 109..227 中心 168；拼图头 0 起点边缘峰 197（≠168!）
→ raw = 374-168 = 206；正确 d_button = (374-197)/2.14 = 83
→ raw 与正确值的差: head0-button_center = 29px 的偏置 × 也被 scale 放大了
r5: raw=380 → 若 head0≈button_center+29=button_center+29, 
    d_button = (raw-29)/2.14 = 164.5 → 滑 178 又过了。
结论: 不该除 scale 后直接滑，而是 (raw - (head0-button_center)) / scale。
head0-button_center 需实测，无法盲算 → 放弃换算，改用**逐步逼近**:
  1) 滑 raw/2.14（保守低估）
  2) 截图差分找拼图头新位置 vs 缺口 → 精确补滑（1:1 补差/scale，迭代 2 次）
每次补滑都用「拼图头实际位置 vs 缺口屏幕位置」的屏幕差 ÷ scale。
"""
