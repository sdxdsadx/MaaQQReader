"""顶部行 OCR='去体验9秒可立即领奖|跳过'（一整行文本含「跳过」子串）。
_has_text('跳过') = True → 分支命中 → tap_feature(skip_key)。
但 tap_feature 需要 locator 定位「跳过」——MAA OCR expected='跳过' 对整行
'去体验9秒可立即领奖|跳过' 做 contains 匹配应该命中并返回整行 box
(444,18,264)→中心 (576,32)。点 (576,32) 落在'跳过'文字附近应该对。

为什么没生效？看 run4 日志里 skip 分支是否执行——搜 step.advance。
如果执行了 tap_feature 但 locator 失败（如 roi 限制），会报'未定位到特征'。"""
from pathlib import Path

rows = Path(r"G:\project_X\runtime\logs\today_ad_run4.log").read_text(encoding="utf-8", errors="replace").splitlines()
for r in rows:
    if "step.advance" in r or "page.observed" in r:
        print(r[:150])
