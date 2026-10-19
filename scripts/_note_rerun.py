"""状态是 AD_PLAYING → advance 分支应该跑到「去体验+跳过」提前分支。
但 observe 189 全是同页 → 没生效。为什么？
看执行顺序：AD_PLAYING 分支开头有 initial_wait（40s wait 一次），
然后 claim_exit/completed/accelerate/continue/force_exit 检查…
「去体验+跳过」分支我插在哪？——插在 is_live 判断**之前**（第 321 行前）。
但前面还有 continue_text='继续观看' 检查！这页没有「继续观看」，无碍。
claim_exit='去领取奖励'？无。accelerate？无。force_exit？无。
那应该能到 skip 分支。除非——patch 后没重启 run4？run4 是 patch 后启动的，
应该带新代码。除非 patch 文件写入时 run4 已 import 旧模块——run4 启动于
patch 之前？时间线：run4 21:xx 启动，patch _patch_ad_browse_skip 在 run4
启动**之后**！我搞错顺序了：skip patch 是在 kill run4 后才提交的。
→ run4 跑的是只有 live_texts 修复（008cff9）没有 skip 提前分支的代码。

重新跑一轮验证 skip 分支。"""
print("重跑验证")
