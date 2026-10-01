"""GameFlow 13:15 启动已 33 分钟，app 还在 AI 朗读页（我杀 audio_retry2
run_task 时只杀了 run_task 父子，MAA 挂机发生在 run_maa_ad 里已退？
不对：AI 朗读页仍在播放（第334章）说明听书没被中断——run_task 被杀时
legacy 子进程树可能未完全终止（taskkill /T 杀了 run_task+子，但听书播放
是 app 内状态，退出流程 AudiobookExitReaderPage 没跑 → 播放继续）。
GameFlow 卡在朗读页找游戏入口（同昨天问题，等 Codex 的 #13 入口修复）。
决策：GameFlow 会 40min 超时（13:55），期间不动。听书挂机其实已在
13:14-13:45 达成 30 分钟档（虽然 run_task 被杀），直接手动去奖励页验收
听书奖励 + 手动退出朗读页给 GameFlow 让路？GameFlow 还在跑，等它超时后
一起手动收尾。等待。"""
print("GameFlow 等待超时中，听书已达 30min 档")
