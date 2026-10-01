"""断链只有 AdReturnStable→[Anchor]LevelAfterAd（<Anchor> 前缀是 MAA
跳转语法还是笔误？）。但这跟听书 36s 失败未必相关。
daily log 里 04:53:15 后听书段的具体报错被 GameFlow 的输出覆盖了？
重新精确定位：找 DailyAudiobookFlow start 04:53:15 之后 30 行内的
success/status JSON 行。"""
from pathlib import Path

log = Path(r"G:\project_X\runtime\logs\daily_all_20260913.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
idx = next(i for i, r in enumerate(rows) if "DailyAudiobookFlow start 04:53:15" in r)
for r in rows[idx:idx + 25]:
    print(r[:170])
