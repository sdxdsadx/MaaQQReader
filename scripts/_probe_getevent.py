"""M 复盘: raw=244（新题）滑 244 失败。E0 实验证明单段 swipe 跟手且会回弹——
触摸没问题、回弹=校验拒绝。距离也验证过了（r6 累计 339≈目标331）。那拒绝
的原因只剩: **行为轨迹指纹**（每次 swipe 都是一次性的匀速直线，无加速度变化、
无停顿、无 y 抖动——纯机器特征）。

人类滑动特征: 加速-匀速-减速-微过冲-回调；y 轴自然漂移；总时长与距离非线性。

终极实现: 把 swipe 拆成 MAA 不支持的连续 move 流 → 换 adb getevent/sendevent
注入原始触摸事件序列（风险高），或者**用 minitouch 风格的多段短 swipe 无缝拼接**
不可行（down-up 分段会回弹）。

最实际方案: MAA 的 swipe 内部是「按下-系列 move-抬起」——看 MaaFramework
的 swipe 是否支持加速度控制…不可控。
→ 改用 adb sendevent 原始事件流构造拟人轨迹（全套：DOWN、多步 MOVE（变速），
UP），绕过 input swipe 的匀速直线。MuMu 支持 sendevent（root 模拟器）。
先探测触摸设备: adb shell getevent -pl 找 touchscreen 设备。
"""
import subprocess

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"
r = subprocess.run([adb, "-s", dev, "shell", "getevent", "-pl"], capture_output=True, text=True, timeout=20)
print(r.stdout[-3000:])
