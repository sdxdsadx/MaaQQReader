"""taskkill /T 把 daily_all（PID 84076 父进程）也杀了——只剩 ❌ 行，
链路已停。诊断：为什么 run_task 在 legacy 4000 后挂 25 分钟不退？
对比昨天成功场景：同样的 legacy 调用 12:47 失败 4000。
区别：昨天模拟器是"实例0 + QQ阅读启动"；今天也是实例0+QQ阅读 pid 2482。
但今天 app 在书城页而非书架！DirectReadingFlow 第一步书城页找不到节点。
但 4000 = MAA 任务失败退出，run_task 应立即返回。
看 run_task.py legacy 分支的等待逻辑——可能是 legacy_run 的 subprocess
communicate 卡住（MAA stderr 管道没关）。
重点不是修复（交给 Codex），是恢复链路：重新跑 daily_all，跳过阅读
（阅读 35min 挂机本来就是大头），先跑 听书/游戏/广告。"""
from pathlib import Path

print("重跑 daily_all 跳过阅读")
