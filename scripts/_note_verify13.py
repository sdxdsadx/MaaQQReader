"""实机验收 Codex #13 修复：
①run_task 超时杀树：把 ReadingWaitOneMinute 临时改短没法测 4000 场景——
  直接跑 DirectReadingFlow（app 现在在奖励页=非书城非书架，新 EnsureShelfOrGoto
  节点应该 OCR「排行榜|男生|免费」失败→走书架分支……等等，奖励页也不在
  底部导航。看修复逻辑：EnsureShelfOrGoto 匹配书城特征→点书架。
  奖励页无这些特征→节点失败→next 走原入口？MAA next 是 OR 顺序匹配。
  直接实跑看结果——若 SUCCESS 则阅读+验收一并完成（今日阅读10分钟+听书时长
  已在挂机中达成）。
先跑阅读。"""
print("实跑 DirectReadingFlow 验收")
