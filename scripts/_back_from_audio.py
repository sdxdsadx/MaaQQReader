"""异常：02:47 应切游戏任务，但屏幕还停在 AI 朗读页（第322章 01:51/07:27
播放中）——DailyAudiobookFlow 02:47:27 exit=0 但听书页面没退出！
AudiobookPauseAfterTrial 暂停了播放但进程收尾没回主页？而 DailyGameFlow
启动后找不到游戏入口（被 AI 朗读页挡住）→ 空转。
且听书播放仍在继续（01:51/07:27 是进度条）——没有暂停成功。

决策：听书任务 exit=0 已达标（32 分钟挂机完成），当前遗留播放页。
游戏任务现在必然找不到入口在空转。手动按 BACK 退出朗读页到主页，
让游戏任务能找到入口（游戏任务 timeout 40min，还有时间恢复）。"""
import subprocess
import time

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"
for i in range(2):
    subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=15)
    time.sleep(2)
print("BACK x2 → 回到书架/主页")
