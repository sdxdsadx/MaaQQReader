"""好消息：书架页重启听书后，app 已进 AI 朗读页（听书挂机中）——
书城页假设部分证实：从书城页直接跑会 4000，从书架页跑就正常。
（run_task 无输出属正常——legacy 只在结束时打 JSON。）
当前听书 32min 挂机中，约 14:05 结束。
趁挂机期把两个问题提交 issue 给 Codex：
①legacy 4000 后 run_task 挂死 25 分钟不退（阅读任务实锤，进程树卡在
  run_task 不退出，daily_all 被阻塞，需手动 taskkill）
②入口节点不覆盖书城页：app 停书城时 DirectReadingFlow/DailyAudiobookFlow
  直接 4000（今天两次实锤），需补书城→书架入口或把入口节点加进两个流程
先提交 issue。"""
print("提交 issue")
