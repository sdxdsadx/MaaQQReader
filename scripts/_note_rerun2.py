"""✅ 点「坚持退出」→ 回到奖励页（进度 3/12，今日已获赠币140）！
链路验证：跳过→弹窗→坚持退出→回奖励页 全通。
刚才 7 轮 run_task 都卡是因为「去体验」分支命中后 tap_point(684,24) 的
点击无效？活体手动点 (684,24) 有效（弹出确认框）……
但 run7 里「坚持退出」出现后 force_exit 分支应该点它——不，我的新代码
顺序：检测「坚持退出」在**去体验分支内部**，但分支条件是 has('去体验')；
弹窗出现时顶部行「去体验9秒…」还在（弹窗半透明盖在广告上）→ 分支命中 →
先查'坚持退出' → tap_feature(force_exit_key)。force_exit_key 是 OCR 特征
「坚持退出」→ locator 应命中…但 run7 里没成功。

再想：run7 里 tap_point(684,24) 每轮都点 → 每轮都弹确认框 → 下轮
has('坚持退出') → 点 force_exit_key —— force_exit 的 locator 是否有 ROI
限制？MaaFeatureLocator OCR 全屏找，应该能中。但 run7 observe 157 循环
弹窗都没出现（尾部 OCR 无'确定要退出'）——可能 tap_point 后又立刻点了
其他地方关掉弹窗？不深究了，活体已证明人工链路通。

关键修复方向改为：跳过后弹窗必现，让分支在**同一轮内**处理：
先点跳过，等 2s，再截屏判断弹窗并点坚持退出——需要同轮多动作。
MAA adapter 的 Action 是单动作。改为用 settle 机制：跳过后设
ad_exit_settle_until=now+2.5 → 下轮进入 settle>0 返回 wait——不行。
新数据键 browse_skip_at: 跳过后记录；下轮若弹窗在且 browse_skip_at>0
→ 点坚持退出。当前代码顺序其实已支持（下轮进分支先查坚持退出）。
但 run7 没成功——怀疑 tap_point(684,24) 在 run 里点击被 MAA 坐标缩放
（screencap 720x1280 vs 物理分辨率）？手动 input tap 用的是物理坐标同 720。
真实原因待查，但先直接重启 run_task 试一次（现在代码都齐了）。"""
print("代码已齐，重跑 run_task 验证")
