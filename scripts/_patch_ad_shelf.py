"""弹窗已不在。当前屏是普通书城页、runner 链路判 HOME。
那 run_task 循环失败期间到底什么状况？也许在启动早期弹窗挡住时
HOME 确认失败 → _recover 循环（back/重进），弹窗消失后循环恢复了但
start_condition 评估阶段 phase 还在 START——而 HOME 动作点
home_ocr_reward_entry（「本周阅读时长|再读N分钟领赠币」）在书城页找不到
→ TAP_FEATURE 失败 → 循环。哦！这就是卡点：
**HOME 在书城 tab 找不到奖励入口**（入口在书架 tab），start_condition
其实满足（HOME），ready 不满足（没有「立即观看/看小视频领好礼」），
adapter 在 HOME 时 tap home_ocr_reward_entry 找不到 → 空转。

修复（与阅读任务相同套路）：HOME 动作先点底部「书架」tab（y≈1263, x=89）
固定坐标兜底，或 OCR「书架」>1100 区域。改 ad.py 的 HOME 动作。
最小实现：Action.tap_feature(home_ocr_reward_entry) 失败后加固定点击。
但 plan 是静态 Action。改 adapter.advance 在 REWARD_HOME/HOME 分支前
加：state==HOME 且找不到 reward_entry 时先点书架 tab（新 Action.tap_point(89,1263)）。

实施：ad.py advance() HOME 分支（actions dict 里 HOME: tap_feature...）改为
在 AdTaskAdapter.advance 里拦截 state is PageState.HOME：
if not has(本周阅读时长|再读N分钟) → 返回 tap_point(89,1263) (书架 tab)。
用 existing 数据键避免重复点（ad_shelf_tab_taps 次数限制 3 次）。"""
from pathlib import Path

p = Path(r"G:\project_X\qqreader\tasks\ad.py")
src = p.read_text(encoding="utf-8")

old = """    def advance(self, context: TaskContext) -> StepResult:
        state = context.decision.state if context.decision is not None else None
        settle = float(context.get("ad_exit_settle_until", 0)) - context.now
        if settle > 0:
            # Close is asynchronous: a fresh screenshot can still contain the
            # outgoing ad. Never queue Back while that close is in flight.
            return self._execute(Action.wait(settle), context)
        # GAME_ENTRY is the same reward page when its game row is visible.
        if state in (PageState.REWARD_HOME, PageState.GAME_ENTRY):"""

new = """    def advance(self, context: TaskContext) -> StepResult:
        state = context.decision.state if context.decision is not None else None
        settle = float(context.get("ad_exit_settle_until", 0)) - context.now
        if settle > 0:
            # Close is asynchronous: a fresh screenshot can still contain the
            # outgoing ad. Never queue Back while that close is in flight.
            return self._execute(Action.wait(settle), context)
        # 书城 tab 上没有奖励入口（home_ocr_reward_entry 在书架 tab）。
        # HOME 状态下找不到入口文案时先点底部「书架」tab（issue: 书城页空转）。
        if state is PageState.HOME:
            has_entry = any(
                needle in text
                for text in context.observation.ocr_texts
                for needle in ("本周阅读时长", "分钟领")
            )
            taps = int(context.get("ad_shelf_tab_taps", 0))
            if not has_entry and taps < 3:
                context.update_data(ad_shelf_tab_taps=taps + 1)
                return self._execute(Action.tap_point(89, 1263), context)
        # GAME_ENTRY is the same reward page when its game row is visible.
        if state in (PageState.REWARD_HOME, PageState.GAME_ENTRY):"""

assert old in src, "anchor not found"
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("ad.py HOME→书架 tab 兜底已加")
