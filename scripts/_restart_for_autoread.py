"""又是「人声朗读中无法开启自动阅读模式」——听书会话还挂着！
（昨天全职法师的听书播放一直没停。）
听书会话退出路径：之前发现右上角迷你播放器点不动；昨天成功清掉是重启 app。
但重启会打断当前 DirectReadingFlow 状态（无所谓，阅读任务已结束）。
另外这也说明：**auto_read 脚本应先处理听书会话**（issue #13 的书城适配
之外的第三个入口问题——朗读页/听书会话检测）。
现在的实操路径：重启 app → 书架 → 点开书进正文 → 跑 auto_read 10min。
这本身就是给 issue 补充证据 + 临时解法。重启。"""
import subprocess
import time

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"
subprocess.run([adb, "-s", dev, "shell", "am", "force-stop", "com.qq.reader"],
               capture_output=True, timeout=20)
time.sleep(3)
subprocess.run([adb, "-s", dev, "shell",
                "monkey -p com.qq.reader -c android.intent.category.LAUNCHER 1"],
               capture_output=True, timeout=30)
time.sleep(14)
print("app 重启完成")
