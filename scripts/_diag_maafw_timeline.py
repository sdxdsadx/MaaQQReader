"""资源加载状态 3000 = SUCCEEDED，节点也存在于 json。但 MAA 运行时报
invalid node id。差异点：MAA v5.12.3 要求 pipeline 节点名匹配
「tasker post 的 entry 必须是 interface/pipeline 定义的节点」——同名存在。
那 invalid node id 的另一个可能：**该 json 文件没被 bundle 加载**（文件名/
编码问题）或 resource 加载时校验失败被静默忽略？检查 MaaResourcePostBundle
的返回（resource_id）和加载 warning。也直接对比 DailyAdFlow 是否也在同一
json 里——若 DailyAdFlow 之前跑成功过（是的！昨天），说明 bundle 加载正常，
仅 DirectReadingFlow 节点有问题。

再仔细看节点定义: {"action":"StartApp",...} — StartApp 是合法 action。
next 三个节点存在。interrupt? 没有。

啊，等等——MAA 的错误是 PipelineTask::run「invalid node id, handle error」
——这是**运行时**错误：post_task 后任务跑起来了，在执行链中某个 next 节点
句柄无效？日志 20:57:42 post_task → 20:58:06 invalid node id（24 秒后）——
说明前面的节点在跑（LaunchQQReader? DirectReadingFlow 是 StartApp →
next 三个 Terminal 节点）。24 秒内执行了 StartApp + find book？
看更完整的 maafw 日志时间线。"""
from pathlib import Path

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
# 找 20:5 时间段的 INF/WRN/ERR
for r in rows:
    if r.startswith("[2026-09-12 20:5") and ("WRN" in r or "ERR" in r or "INF" in r):
        print(r[:220])
