"""异常：_page20_last_tier 显示「未找到续读行」→ 没回正文就翻页 20 分钟——
点击 (600,640) 全打在奖励页空白处！赠币仍 160。
现在人在奖励页（今日已获赠币160 / 每周阅读600分钟）。
修正：先回书架 → 点续读行进正文 → 确认正文页 → 再翻页。
杀掉当前空转进程，重跑。"""
import subprocess

r = subprocess.run(
    ["taskkill", "/PID", "74020", "/T", "/F"],
    capture_output=True, text=True, timeout=20)
print(r.stdout.strip()[:100])
