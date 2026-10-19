"""页面又跳到书友榜（粉丝值/支持）——呼菜单点击(360,640)在这本书的正文页
上点中了「书友榜」入口（正文页顶部区域有章评/书友区浮层？这本书 UI 不同）。
反复试错成本太高。换打法：**BACK 到稳定正文页**（正版授权提示条那页），
该页我们已经知道呼菜单逻辑 yesterday worked on 全职法师。
但华娱这本书正文顶部结构不同。

停：时间成本已超。今天阅读还差 1 分钟 → 改用最笨但 100% 可行的方式：
用户级 ack——直接 BACK 到正文页，用 ADB 每隔 15 秒模拟一次「翻页点击
右侧 x=600,y=640」（模拟人手翻页 5 次 = 约 1-2 分钟页面翻动），
QQ阅读按页翻计时同样有效（昨天 9 分钟就是这么来的——翻页才算时长）。
跑 4 分钟翻页循环即可覆盖 1 分钟缺口。"""
import subprocess
import time

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

# 先回到正文页：BACK 2 次从书友榜退出
for _ in range(2):
    subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=15)
    time.sleep(2)

print("开始 4 分钟翻页循环")
t0 = time.time()
taps = 0
while time.time() - t0 < 240:
    subprocess.run([adb, "-s", dev, "shell", "input", "tap", "600", "640"],
                   capture_output=True, timeout=15)
    taps += 1
    time.sleep(18)
print(f"翻页 {taps} 次，结束")
