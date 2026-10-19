"""确认：广告任务超时原因=启动时 app 停在游戏中心页（非 HOME），
UNKNOWN 空转 40min。这两个失败（游戏+广告）都源于游戏中心页无恢复路径。

修复：ad.py advance() 加 UNKNOWN 兜底——连续 N 次 UNKNOWN 时 BACK
（游戏中心→BACK 回书城/书架→再 BACK 回 HOME）。这比每个异常页面单独
适配更通用。等 Codex 修 #12 时一并？#12 是 game.py；UNKNOWN BACK 兜底
是 ad.py——我自己快速修掉（10 行内），pytest 后提交。

同时把广告任务欠的层数补跑：先手动把 app 恢复到主页，再跑 DailyAdFlow。"""
from pathlib import Path

p = Path(r"G:\project_X\qqreader\tasks\ad.py")
src = p.read_text(encoding="utf-8")

anchor = """    def advance(self, context: TaskContext) -> StepResult:
        state = context.decision.state if context.decision is not None else None
        settle = float(context.get("ad_exit_settle_until", 0)) - context.now
        if settle > 0:
            # Close is asynchronous: a fresh screenshot can still contain the
            # outgoing ad. Never queue Back while that close is in flight.
            return self._execute(Action.wait(settle), context)"""
add = """        # UNKNOWN 兜底：连续 6 次未识别（游戏中心等异常页）时按返回键
        # 逐层退出，直到回到 HOME/书架可识别页。
        if state is None:
            unknowns = int(context.get("ad_unknown_backs", 0))
            if unknowns >= 6 and unknowns < 14:
                context.update_data(ad_unknown_backs=unknowns + 1)
                return self._execute(Action.press_back(), context)
            context.update_data(ad_unknown_backs=unknowns + 1)
        else:
            context.update_data(ad_unknown_backs=0)"""

assert anchor in src
src = src.replace(anchor, anchor + "\n" + add)
p.write_text(src, encoding="utf-8")
print("ad.py UNKNOWN BACK 兜底已加")
