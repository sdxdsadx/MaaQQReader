"""修 import 顺序重提 issue。"""
import subprocess
import sys
from pathlib import Path

body = """## 背景（2026-09-15 daily_all 实测）
DailyAdFlow 40min 超时（exit=2, final_state=GAME_ENTRY, steps=243）。
日志反复出现：phase.prepare「OCR:立即观看 未命中」→ REOBSERVE 死循环。
app 实际停在奖励页，但「立即观看」入口被今日游戏卡挤到页面下方（需下滑），
任务链没有滚动查找节点，观察-重观察死循环到超时。

## 关联
issue #15 已交付 qqreader/reward/nav.py 的 find_watch_entry(client)
（滚动查找「立即观看」），但只在独立监督脚本里用过，未接入 ad.py 主链。

## 期望修复（Codex）
1. qqreader/tasks/ad.py 入口阶段（prepare/REOBSERVE 前）接入滚动查找：
   复用 nav.find_watch_entry 逻辑（最多 8 次下滑，找到即点，找不到报可读错误）
2. 回归测试：fake client + OCR fixture 覆盖「入口在首屏」「入口需下滑 N 次」「入口不存在」
3. pytest 全量通过；git add 明确文件 commit fix(ad): scroll-find watch entry via nav module，不 push
4. close 本 issue 附摘要

证据：runtime/logs/daily_all_20260915_DailyAdFlow.log（REOBSERVE 循环）
"""
p = Path(r"G:\project_X\.hermes\issue16_body.md")
p.write_text(body, encoding="utf-8")
r = subprocess.run(
    ["gh", "issue", "create", "--repo", "sdxdsadx/MaaQQReader",
     "--title", "DailyAdFlow 入口无滚动查找：立即观看被挤到屏下时 REOBSERVE 死循环超时",
     "--body-file", str(p)], capture_output=True, text=True, timeout=120, errors="replace")
out = (r.stdout or "") + (r.stderr or "")
print(out.strip()[-200:])
