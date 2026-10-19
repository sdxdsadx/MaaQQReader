"""v4 r1 深诊断 2: 书城页 126 observe 无 step.advance——它在哪个 phase？
推演: 书城页判 UNKNOWN → needs_recheck → 确认阶梯（confirmer）→ 若确认不出
任何状态 → popup_detected? → 无弹窗 → streak>=max_unknown_rechecks → _recover。
但日志没有 page.unknown / step.advance 行 = verbose 输出里只有 observe。
看 run_task 的 _record 是否打到 stdout（diag 事件只在结束才 dump?）。
验证: result.diagnostics[-60:] 在结束时打印——中途只打 observe。
所以日志无事件行 ≠ 无事件。看结束时的 diagnostics。

当前轮 watch 何时触发 watchdog? 尾行持续变化（observe 计数变）→ 不触发。
→ 卡死是「确认阶梯内部空转」，轮询间隔 pause_unknown。
检查 confirmer 的确认阶梯: 它对书城页每次都失败但不清计数?

关键点: 书城页 OCR 有「男生」——查 HOME 定义是否含「书架」required 而
书城页没有「书架」→ HOME 不确认; UNKNOWN 空转。
修复方向: HOME 的 OCR 特征加「男生|女生」频道 tab（或书城页归 HOME）。
先看 HOME 定义 + confirmer 逻辑 + max_unknown_rechecks 后的 _recover 行为。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runner = (ROOT / "qqreader" / "runner" / "runner.py").read_text(encoding="utf-8")

# _recover 行为
m = re.search(r"def _recover\(.*?(?=\n    def )", runner, re.S)
print("=== _recover ===")
print(m.group(0)[:1500] if m else "not found")
