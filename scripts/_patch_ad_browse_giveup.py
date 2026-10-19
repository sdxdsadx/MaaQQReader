"""「去领取奖励」按钮消失了，广告页死循环——这是典型拉活广告：跳过弹窗
选「去领取奖励」后要求去体验（跳第三方）才发奖，体验回来才发；直接跳过
= 放弃奖励。
此广告无法静默完成（需要跳第三方 app 交互），处理：按用户既定方针——
**直接跳过该广告，继续下一条**。用「确定要退出吗」弹窗的另一按钮
「坚持退出」/直接 BACK 退出，回奖励页点下一条。
实现 + 固化：浏览广告检测到「去体验」时，先点跳过(684,24)，弹窗若出现
「坚持退出」点它（放弃奖励）；若「去领取奖励」出现则等 10s 再试一次，
仍失败就「坚持退出」。这逻辑进 _handle_browse_ad。

简化实现：advance 的去体验分支改为：
1. tap_point(684,24) 跳过
2. settle 后若确认框出现：有「坚持退出」→ 点之；否则 BACK。
加 browse_exit_tries 防循环。"""
from pathlib import Path

p = Path(r"G:\project_X\qqreader\tasks\ad.py")
src = p.read_text(encoding="utf-8")
old = """            if self._has_text(context, "去体验") and self._has_text(
                context, self._skip_text
            ):
                # 「跳过」在顶部提示行（无独立 asset），用实测坐标点击。
                return self._execute(Action.tap_point(688, 30), context)"""
new = """            if self._has_text(context, "去体验"):
                # 浏览型拉活广告：跳过会弹「确定要退出吗」，两个按钮语义：
                # 去领取奖励=跳第三方体验后再领（无法自动化）；坚持退出=放弃。
                # 策略：先点跳过；弹窗若已有「坚持退出」则点它；否则 BACK 兜底。
                if self._has_text(context, "坚持退出"):
                    tries = int(context.get("browse_exit_tries", 0))
                    context.update_data(browse_exit_tries=tries + 1)
                    return self._execute(Action.tap_feature(self._force_exit_key), context)
                if self._has_text(context, "确定要退出吗"):
                    waits = int(context.get("ad_play_waits", 0))
                    context.update_data(ad_play_waits=waits + 1)
                    if waits >= 6:
                        return self._execute(Action.press_back(), context)
                    return self._execute(Action.wait(2.0), context)
                return self._execute(Action.tap_point(684, 24), context)"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("浏览广告 放弃策略 已固化")
