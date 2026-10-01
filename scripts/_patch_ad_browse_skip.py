"""这是昨天 20:53 那次失败运行的退出通知（旧进程），无新信息。
当前焦点：浏览型广告（喇叭广告）求解。活体 OCR 已拿到关键布局：
- 顶部 y=18：「去体验9秒可立即领奖|跳过」（跳过按钮在此行内！x≈444+264=708 右端）
- y=442：去体验9秒（大按钮）
- y=730：去体验
- y=896/1194/1222：上滑或点击跳转
- 无 X 关闭按钮（左上角只有'小'(logo)和'反馈'）

处理策略修正：这类广告必须「点跳过」或「去体验9秒等倒计时」。
live 下滑处理不适用（页面不滚动内容固定）。改：
- 加 browse 跳过：识别「跳过」→ 点击（顶部 y=18 那行已含「跳过」，
  skip_text='跳过' 的 tap_feature 应能命中——为什么之前没点到？
  因为 is_live=True 走了 _handle_live_ad，没到 skip 分支！）
- 顺序问题：live_texts 含「去体验」后 is_live=True 优先于 skip。
  但这广告的「跳过」在顶部——skip 分支在 is_live 之后被短路。

修正：把「跳过」检查提到 is_live 处理之前（skip 是通用安全的）。
在 advance() 里 is_live 判断前加：
if self._has_text(context, self._skip_text) and "去体验" in joined:
实际更简单——把 offer 检查同样提前？最小改动：仅对 skip 提前。
但「跳过」在普通视频广告也出现（原本就在 is_live 后），提前会影响直播广告
（直播页也可能有「跳过」字样？直播文案是「进入直播间」，跳过提前点击
可能误点）。折中：只在「去体验」存在时把 skip 提前。"""
from pathlib import Path

p = Path(r"G:\project_X\qqreader\tasks\ad.py")
src = p.read_text(encoding="utf-8")

old = """            # Modal buttons remain actionable even when the live ad is visible
            # behind the overlay. Reobserve after each action before scrolling.
            if is_live:
                return self._handle_live_ad(context)"""
new = """            # 「去体验N秒」浏览型广告：无 X、页面不滚动，「跳过」在顶部提示行。
            # 必须先点跳过；live 下滑处理对它无效（页面内容固定）。
            if self._has_text(context, "去体验") and self._has_text(
                context, self._skip_text
            ):
                return self._execute(Action.tap_feature(self._skip_key), context)
            # Modal buttons remain actionable even when the live ad is visible
            # behind the overlay. Reobserve after each action before scrolling.
            if is_live:
                return self._handle_live_ad(context)"""

assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("去体验+跳过 提前分支已加")
