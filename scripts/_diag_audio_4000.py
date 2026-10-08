"""听书 solo 跑了 32 分钟后 4000 失败——不是立即失败，是挂机结束后
收尾阶段崩。4000 出现在 AudiobookExitReaderPage（Codex 新加的
ClickKey key=4 节点）附近概率最大。看旧项目 debug 日志最新 maafw.log
的 ERR 行定位。"""
from pathlib import Path

# run_maa_ad --runtime G:\project_X\dev → dev\debug\maafw.log
p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
print("行数:", len(rows))
errs = [(i, r) for i, r in enumerate(rows) if "[ERR]" in r]
print("ERR 行数:", len(errs))
for i, r in errs[-6:]:
    print(r[:180])
