# QQReader 更新日志

## 2026-09-26 · 修正阅读卡 OCR 误识与滑动验证

**触发**：`runtime/logs/gui_DailyReadingFlow_20260925_203458.log` 在完成阅读后报“奖励页未找到‘每日阅读领赠币’卡片”；同次 Maa 日志 21:13:21~37 多帧读到“每日阅读领赠市”与两枚“领取”按钮。`runtime/logs/gui_DailyAdFlow_20260925_221713.log` 报滑动 6 轮后验证码仍在。

| 模块 | 原因与修改 |
| --- | --- |
| 阅读领奖 | 标题匹配只接受“币”，导致 OCR 误读为“市”时找不到实际存在的卡片；`reading_card_bounds` 只增加这一种已实测的字形变体。提交同时保留本地已实现的服务器时长同步等待、刷新与带时间戳证据截图，避免阅读完成后过早判定不可领。 |
| 滑动验证 | 截图的 Canny 最强列约 `x=492` 是缺口左侧边缘；改为汇总右侧强边缘，离线目标约 `x=532`。每次验证码最多滑动 15 轮，守卫只启动一次完整求解，失败后等待人工。 |

**改动文件**：`qqreader/tasks/reading_reward.py`、`qqreader/captcha/slide.py`、`qqreader/captcha/factory.py` 及对应两份测试。

**验证**：Luna 独立执行 `py -3.10 -m pytest tests/test_reading_reward_claim.py -q`，6 项通过；独立工作树执行 `py -3.10 -m pytest tests/test_reading_reward_claim.py tests/test_qqr29_captcha.py -q`，19 项通过、1 项因旧截图不存在而跳过。日志 OCR 已核对；修复后尚未重跑 35 分钟 GUI 阅读或真实滑动验证码。

**未覆盖 / 遗留**：真实设备是否接受新的滑动落点、再次误读卡片标题时是否能完成实机领奖，需下一次 GUI 运行确认；15 轮滑动需给广告任务足够超时时间。

**回滚**：回退本次提交即可；不涉及机器配置或用户运行数据。
