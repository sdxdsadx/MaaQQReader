"""重大进展：点击跳过 → 弹出「确定要退出吗? 去领取奖励」对话框！
这正是 claim_exit_text='去领取奖励' 的处理路径——点它退出广告并领奖。

那为什么 run5 里 skip 分支没执行？检查 run5 用的代码是否含 skip 提前分支——
commit 7e2603d 在 run5 启动前已提交，run5 应该有。看 run5 里是否真有点击
「跳过」的动作迹象（弹窗在 run5 尾部 OCR 没出现？run5 尾部 observe 151
无'确定要退出'）。可能 tap_feature('跳过') locator 失败（ad_skip asset=None
——catalog 里根本没有这个 asset！tap_feature 对未知 feature 走 point fallback？
看 _tap_feature_or_point / MaaFeatureLocator 对缺失 asset 的行为——
大概率定位失败 → 无操作 → 循环。

修复：skip 用固定坐标。跳过按钮位置：顶部行内「跳过」≈(688,30)。
加 Action: 在「去体验+跳过」分支直接 tap_point(688, 30)。"""
from pathlib import Path

p = Path(r"G:\project_X\qqreader\tasks\ad.py")
src = p.read_text(encoding="utf-8")
old = """            if self._has_text(context, "去体验") and self._has_text(
                context, self._skip_text
            ):
                return self._execute(Action.tap_feature(self._skip_key), context)"""
new = """            if self._has_text(context, "去体验") and self._has_text(
                context, self._skip_text
            ):
                # 「跳过」在顶部提示行（无独立 asset），用实测坐标点击。
                return self._execute(Action.tap_point(688, 30), context)"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("skip 改固定坐标 (688,30)")
