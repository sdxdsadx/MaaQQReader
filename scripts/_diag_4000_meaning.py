"""dev\debug\maafw.log 无 ERR 且 22545 行（含游戏轮内容，是共享文件）。
4000 的定位难。换思路：run_maa_ad.py 的 4000 是「任务没找到出口」？
看旧项目 run_maa_ad.py 对 status 的定义。"""
from pathlib import Path
import re

src = Path(r"G:\project_X\_backup_old_project_20260909_200716\tools\run_maa_ad.py").read_text(encoding="utf-8")
for m in re.finditer(r"(4000|status)", src):
    s = max(0, m.start() - 80)
    line = src[s:m.end() + 120].replace("\n", " ")
    print(line[:200])
    print("---")
