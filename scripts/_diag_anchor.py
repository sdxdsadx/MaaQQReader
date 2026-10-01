"""日志错位真相：DailyAudiobookFlow start 04:53:15 之后紧跟的是
[run] task=DailyGameFlow 的输出——**daily_all.py 的 log append 是并发交错
的**：Audiobook run_task 36s 失败退出后，它的 stdout 缓冲写在 GameFlow
启动之后才 flush 进文件（或轮转冲突）。总之：真正的听书失败原因没写进
日志——36s exit=2 大概率还是 json/资源级错误。

直接手动单独跑 DailyAudiobookFlow 拿干净输出。先停当前 daily_all
（GameFlow 正在跑，先让它跑？GameFlow 是本次修复的验证重点，让它跑完）。
听书失败根因排查：MAA json 断链 AdReturnStable→[Anchor]LevelAfterAd
（<Anchor> 不是节点名，是笔误残留）。先修这个断链——它会让 MAA 资源
加载失败 → 所有 legacy flow 36s 内退出。听书上轮 04:53 挂了，
但 02:15 那轮成功——说明断链是 Codex 第一棒 04:31 改 json 时引入的！
（02:15 时它还没改）。立即修复。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))
node = data["AdReturnStable"]
print("原 next:", node.get("next"))
# [Anchor]LevelAfterAd 不是有效节点——查 LevelAfterAd 是否存在
print("LevelAfterAd 存在:", "LevelAfterAd" in data)
cands = [k for k in data if "LevelAfter" in k or "Anchor" in k]
print("近似节点:", cands)
