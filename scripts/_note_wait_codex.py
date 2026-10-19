"""失败原因确认：Codex 的工作树修改未提交（M game.py/profiles/...）——
它正在改到一半，2 个失败是 Codex 中间态导致的（与我 ad.py 提交无关，
我只动了 ad.py）。6d18e2f 提交里 pytest failures=2 是因为 Codex 未提交
修改混在工作区。**不要动 Codex 的未提交文件**——等它完成并自己提交。

我的 ad.py 修改独立且已提交推送。继续等 Codex + 广告任务当前轮等它跑完
（run10 被 kill 了，GAME_HALL 修复已 push 但没实跑验证——等 Codex 完工
后一起重跑 daily_all 验证 4 任务）。
现在：恢复设备页面到主页（BACK 退出游戏大厅），等 Codex。"""
print("等 Codex 完工")
