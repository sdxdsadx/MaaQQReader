"""run6 仍卡：点击 (688,30) 可能没落准（顶部行 box=(444,18,264)，'跳过'在行尾
x≈660..708, y≈14..34。中心≈(684,24)。之前手动点 (688,30) 成功弹出确认框！
为何 run6 无效？——run6 代码是新的（8ac5ee9）。除非 '去体验' 的 _has_text
匹配…活体 OCR 有'去体验9秒'，'去体验' in '去体验9秒' = True。
skip_text='跳过' in 顶部行 = True。分支应命中并 tap_point(688,30)。

难道 run6 进程跑的代码是启动时加载的旧版？run6 启动于 commit 8ac5ee9 之后…
除非 git commit 后文件内容又被什么改回？查当前 ad.py 内容确认分支还在，
并直接手动 import 测分支：模拟 context 调 advance？太重。
直接活体驱动完整流程（跳过→确认框→去领取→观察进度）证明链路，然后
再用时间戳确认 run_task 的代码版本问题。"""
from pathlib import Path

src = Path(r"G:\project_X\qqreader\tasks\ad.py").read_text(encoding="utf-8")
print("分支在文件中:", "tap_point(688, 30)" in src)
