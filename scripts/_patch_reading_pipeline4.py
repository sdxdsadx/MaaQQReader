"""原因：上一轮成功后 app 停在**正文页**（书已打开），本轮 StartApp 回前台
还是正文页——「去阅读/书架」都识别不到 → 空等超时。

补第三个入口：AlreadyInBook（正文页特征 OCR——正文内容任意，可用「章节标题
<第N章」regex 或点击屏幕中央唤醒菜单？最稳：正文页顶部有 <第N章 标题。
加节点 ReadingAlreadyInBook: recognition OCR expected regex "第\d+章"，
action DoNothing，next=[ReadingWaitOneMinute]（已在书里，直接计时）。

另外 WaitOneMinute post_delay=2100000ms=35 分钟 —— 用户之前要求 1 分钟?
之前修复设定是「整 60 秒」→ 应为 60000。检查被谁改的：LEGACY_TIMING_NODE
按 --minutes 改 post_delay。retry 脚本没传 minutes → 用的 json 原值 2100000？
这可能是旧默认（35min 听书用）。阅读应为 60 秒=60000ms（上几日修复实证 60s）。
一并改 60000。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))

data["ReadingAlreadyInBook"] = {
    "recognition": "OCR",
    "expected": r"第\d+章",
    "action": "DoNothing",
    "post_delay": 500,
    "next": ["ReadingWaitOneMinute"],
    "focus": {"ReadingAlreadyInBook": "已在正文页（上轮遗留），直接进入计时"},
}
data["ReadingWaitOneMinute"]["post_delay"] = 60000  # 60 秒计时（领币要求整分钟）
data["DirectReadingFlow"]["next"] = ["ReadingAlreadyInBook", "RewardGotoReading", "ReadingGotoShelf"]

pf.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("已加 ReadingAlreadyInBook 入口 + WaitOneMinute=60s")
