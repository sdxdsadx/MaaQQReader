"""run_task 还活着（legacy 4000 后 run_task 内部可能在等 MAA post 完成
或重试循环）。等 daily_all 超时（40min）太慢——直接看 run_task 会怎么结束：
run_maa_ad 已打最终 JSON {"success": false, status: 4000}，run_task 应该
立即返回非零。但 run_task 进程还在——它在等子进程退出？
看 run_task 的 stdout（daily_all_<date>_DailyReadingFlow.log 只有 4 行——
run_task 的 [legacy] 输出都进了这个文件，最后是 4000 JSON，之后没新输出。
run_task 可能在 legacy 返回后做"等待稳定"或恢复动作。
不干预，给它到 13:27（40min 超时）。若超时后 daily_all 继续下一任务，
链路仍能走完。等待。"""
print("等待 run_task 40min 超时或自行结束")
