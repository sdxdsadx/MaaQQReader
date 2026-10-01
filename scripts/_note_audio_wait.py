"""真相：AudiobookWaitOneMinute post_delay=1920000ms = 32 分钟挂机！
02:15 启动 + 找书/开书 ~3min + 32min 挂机 ≈ 02:50 结束 + 暂停收尾。
现在应该快完了。但 run_task --timeout-minutes 40 是否涵盖 32min 挂机？
02:15 + 40min = 02:55 截止——紧巴巴。挂机本身是听书任务的设计（攒时长），
无需修改。继续等完成。"""
print("32min 挂机是设计行为，继续等")
