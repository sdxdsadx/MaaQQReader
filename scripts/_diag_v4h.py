"""决定性实验: 模拟 runner 主循环对书城页的处理——
用完整活体 OCR（58 条，含书城/书架）→ 判 HOME confirmed。
但 r1-v5 观测 52 轮没确认 → runner 的 OCR 与我直接跑的不同？
可能差异: run_task 的 MaaPageObserver 是同一 client；我直接跑也一样。
区别在于「r1 运行时」：18:41 那次 r1 的 observe 一直显示 12 条截断的
书城页（y<850 的内容）——底部导航（y=1250）没出现在前 12 条里
但 all_texts 是完整的（58 条）。等等——r1 observe 行只打印前 12 条！
（run_task.py L186 ocr_texts[:12]）所以日志看不到「书架/书城」，
但 recognizer 用的是完整列表。

那为什么 r1 里 state 没确认成 HOME？——需要看 r1 运行时 OCR 是否真的含
底部导航。当时模拟器屏幕和现在一样吗？——r1 运行时截图在哪？
run_task 有 evidence 截图吗？没有 PAGE_ 截图（因为没确认成功）。
但 preflight 有截图。观测每轮的 last_screenshot 被 save_last_screenshot
写到哪？查 DeviceScreencapGuard。

先验证「当前屏幕判 HOME」能否让 runner 走通：直接跑一轮 run_task 看结果。
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = r"D:\python\python.exe"
log = ROOT / "runtime" / "logs" / "diag_run_bookstore.log"
with open(log, "w", encoding="utf-8") as fh:
    p = subprocess.run(
        [PY, "scripts\\run_task.py", "--config", "configs\\qqreader.local.json",
         "--task", "DailyAdFlow", "--timeout-minutes", "6"],
        stdout=fh, stderr=fh, cwd=str(ROOT), timeout=8 * 60,
    )
text = log.read_text(encoding="utf-8", errors="replace")
rows = text.splitlines()
print("总行数:", len(rows))
print("--- 最后 8 行 ---")
for r in rows[-8:]:
    print(r[:150])
print("--- outcome ---")
for r in rows:
    if r.startswith("[outcome]") or r.startswith("[reason]"):
        print(r[:150])
