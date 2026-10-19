"""两个 legacy 流程（阅读/听书）都 4000，但昨天代码+模拟器同一套全 SUCCESS。
4000=MAA 任务执行失败。变化点排查：
①昨天改过 ReadingWaitOneMinute post_delay=2100000（35min）——只影响阅读
②昨天 qq_reader_trial.json 被 Codex/Astra 改过（issue #16 是 Gameflow 仓库，
  不影响本仓库）——但昨天我修过 AdReturnStable 断链、AudiobookExitReaderPage
③今天重启了模拟器（实例0），QQ阅读 pid 2482 刚启动在书城页
最可能：**app 状态不在书架**（书城页），DirectReadingFlow/
DailyAudiobookFlow 的入口节点找不到 → MAA 失败 4000。
昨天入口修复过（ReadingGotoShelf/RewardGotoReading），但可能只覆盖部分页面。
验证：手动把 app 导到书架页，再单独跑一次听书看是否成功——若成功则根因=
入口适配不全（书城页无入口），提交 issue 让 Codex 补书城页入口。"""
print("验证书城页假设")
