"""游戏任务 02:47 启动，我 03:04 才救场（BACK+重启 app 到游戏中心页）。
游戏挂机 20min 从入口稳定算约 03:24+ 收尾，timeout 40min 到 03:27。
等到 03:28 再查。另：把听书遗留播放页问题记录为 issue 交给 Codex——
legacy DailyAudiobookFlow 收尾未退出朗读页（AudiobookPauseAfterTrial
暂停后应 BACK 回主页），导致下一任务 DailyGameFlow 入口被挡。"""
print("等游戏收尾")
