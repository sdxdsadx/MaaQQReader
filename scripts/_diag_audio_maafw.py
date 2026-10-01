"""听书子进程活着（run_maa_ad DailyAudiobookFlow），旧项目 debug/maafw.log
44KB 在写。看它最新节点判断进展。"""
from pathlib import Path

p = Path(r"G:\project_X\_backup_old_project_20260909_200716\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
print("总行数:", len(rows))
for r in rows[-10:]:
    print(r[:165])
