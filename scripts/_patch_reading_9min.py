"""实锤：阅读进度从「再读9分钟」→「再读6分钟」——1 分钟挂机+广告期间的
阅读时长被计入，但 20 赠币要**读满 10 分钟**才发（今日再读6分钟=还差6分钟）。
这不是 bug，是平台规则：阅读奖励=10 分钟一档。

结论：1 分钟流程本身 SUCCESS（链路修复完成），但要拿 20 赠币需挂满 10 分钟。
用 LEGACY_TIMING_NODE 机制：run_task --minutes 10 会把 WaitOneMinute
post_delay 改 600s。跑 10 分钟版拿币。

估算: 已读 4 分钟（9-6+1），再跑 7 分钟稳妥 → --minutes 7。
但 DirectReadingFlow 的 timing node key 是 DirectReadingFlow? 之前 LEGACY_TIMING_NODE
只有 DailyReadingFlow→DirectReadingFlow / DailyAudiobookFlow→AudiobookWaitOneMinute——
post_delay 会改到 DirectReadingFlow 节点本身（StartApp 的 post_delay！）而不是
WaitOneMinute——bug？看 _patch_legacy_pipeline: data[node]["post_delay"]，
node=DirectReadingFlow → 改的是 StartApp 后延时。真正计时在 WaitOneMinute。
→ run_task --minutes 不会改计时！直接改 json post_delay=480000 (8min) 更稳。

做：WaitOneMinute post_delay 60000→540000（9 分钟，覆盖剩余 6 分钟+缓冲），
跑完领币。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))
data["ReadingWaitOneMinute"]["post_delay"] = 540000
data["ReadingWaitOneMinute"]["focus"] = {"ReadingWaitOneMinute": "挂机阅读 9 分钟（时长兑赠币档位）"}
pf.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("WaitOneMinute post_delay → 540000ms")
