"""链路：StartApp → 去阅读 → 点书（ReadingFindBookTerminal 模板匹配成功点击）
→ 开书成功 → 任务返回 SUCCESS。但 **WaitOneMinute 没跑**——ReadingFindBookTerminal
的 next 没接计时链（这是旧 legacy 节点定义；新链修复时我们只在
dev/resource/pipeline/qq_reader_trial.json 改过 DirectReadingFlow 的 next，
找书三 Terminal 的 next 还是空/旧值）。

检查 ReadingFindBookTerminal / ReadingOpenFirstShelfBookTerminal 的 next，
把计时链（ReadingWaitOneMinute → ReadingExitAfterTimer）接上——之前修过
新 G:\\project_I 打包侧，这里是 dev 侧（当初修复时接的是同一文件？看 json）。"""
import json
from pathlib import Path

data = json.loads(Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json").read_text(encoding="utf-8"))
for n in ("ReadingFindBookTerminal", "ReadingFindBookByTitleTerminal",
          "ReadingOpenFirstShelfBookTerminal", "ReadingWaitOneMinute",
          "ReadingExitAfterTimer"):
    node = data.get(n, {})
    print(n, "=> next:", node.get("next"), "| post_delay:", node.get("post_delay"))
