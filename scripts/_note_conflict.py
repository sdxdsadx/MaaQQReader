"""注意：听书挂机（我手动重跑的 audio_retry2 run_task）还在 32min 挂机窗口内
（13:14 启动 → 约 14:05 结束），而 daily_all 的 DailyGameFlow 也在跑——
两者共用同一模拟器！但我杀掉了 daily_all 阅读分支的进程树后，daily_all
本身还活着（跳过阅读版），它 13:15 启动了 GameFlow——GameFlow 会尝试
找游戏入口，但当前 app 在 AI 朗读页（听书挂机中）→ GameFlow 可能找不到入口。
风险：两个任务互相干扰。活体确认 GameFlow 干了什么。"""
print("确认 GameFlow 与听书挂机是否冲突")
