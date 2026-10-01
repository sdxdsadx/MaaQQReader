"""严重发现：日志混串！听书段尾部 observe 72-79 竟是「游戏画面」（修真大道/
青云诀/1元秒杀）——**上一轮 04:47 起 DailyGameFlow 的 observe 写进了同一个
daily_all_YYYYMMDD.log**（多任务共用日志文件，segment 定位按最后 start 行错位）。
真实时序：听书 04:53:15 启动，36s exit=2 是真实的（快速失败）。
而 observe 72-79 是 GameFlow 的（04:53:56 启动后）。

听书快速失败原因要单独看：04:53:15-04:53:51 只有 36s——可能 json
改坏（AudiobookPauseAfterTrial next 引用不存在节点 → MAA 资源加载失败
立即退出）。查 04:53 时段日志 + 验证 json 节点完整性。"""
import json
from pathlib import Path

log = Path(r"G:\project_X\runtime\logs\daily_all_20260913.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
for i, r in enumerate(rows):
    if "04:53" in r and ("Audiobook" in r or "ERR" in r or "success" in r or "status" in r):
        print(r[:170])

# json 节点完整性
data = json.loads(Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json").read_text(encoding="utf-8"))
names = set(data.keys())
bad = []
for k, v in data.items():
    for nxt in (v.get("next") or []):
        if nxt not in names:
            bad.append((k, nxt))
print("断链:", bad if bad else "无")
