"""正文页就绪。启动滑动翻页长跑（补足有效阅读时长到 300 分钟）。
基于凌晨验证：滑动 280 分钟 ≈ 146 分钟有效（52%）。当前有效 155 分钟，
目标 300 → 还需 145 分钟有效 → 滑动时长 ≈ 145/0.52 ≈ 280 分钟。
脚本 = _swipe280b.py（滑动+章尾下一章处理+休息弹窗处理），重命名运行。"""
import shutil

shutil.copy(r"G:\project_X\scripts\_swipe280b.py",
            r"G:\project_X\scripts\_swipe_final.py")
print("脚本已复制 _swipe_final.py")
