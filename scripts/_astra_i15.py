"""astra 模型可用（pong=True，exit=1 是因为输出格式含额外内容但响应正确）。
现在派 Codex(astra) 接力完成 issue #15 收尾：
- slide.py 已修（工作区未 commit）
- nav.py 未写完
- pytest 回归未写
按用户规则：5小时额度到期 → 用 astra。"""
import os
import shutil
import subprocess
from pathlib import Path

brief = """# 任务：接力完成 issue #15（上一棒因额度中断，slide.py 已修好落盘）

仓库 G:\\project_X（QQ阅读自动化，Python 3.8，D:\\python\\python.exe，PYTHONPATH=G:\\project_X，pytest 264+ 全绿）。
GitHub issue #15（sdxdsadx/MaaQQReader）。上一棒进度：qqreader/captcha/slide.py 的缺口检测回退已修好（工作区未 commit，先 git diff 确认）；scripts/live_captcha_auto.py 的 snap() PNG 编码修复未做；qqreader/reward/nav.py 统一导航模块未写。

## 剩余工作
1. scripts/live_captcha_auto.py 的 snap()：Screenshot 对象用 .save(临时路径) 落盘后 read_bytes 转 PNG 再传 detect_slide（裸 .data 直传是坏 PNG）
2. 新建 qqreader/reward/nav.py：goto_reward_page(client) / find_watch_entry(client) / back_to_reward(client) 三函数，OCR 分支导航（特征见 issue #15 描述：开屏跳过/简介继续阅读/正文 BACK/书城点书架(70,1250)/书架入口兑赠币行）
3. pytest 回归：nav 三函数用 fake client + OCR fixture；detect_slide 用 runtime/screenshots/ad_watch/captcha_now.png 真 fixture（fallback 路径也算过）
4. pytest 全量必须通过：cmd /c "set PYTHONPATH=G:\\project_X&& D:\\python\\python.exe -m pytest tests/ -q"（cwd G:\\project_X）
5. git add 明确文件（qqreader/captcha/slide.py qqreader/reward/nav.py scripts/live_captcha_auto.py tests/ 新测试；不要 git add -A）commit 信息 feat(reward): unified navigation + captcha guard pipeline，不 push
6. gh issue close 15 --repo sdxdsadx/MaaQQReader --comment 修复摘要（PS5.1 先 gh issue comment --body-file 再单独 close）
7. 临时脚本用完删（scripts/_tmp* 与 scripts/_diag_issue15_pixels.py）

禁止实机跑 run_task.py（模拟器由监督占用）。中文路径仓库：cwd 用 cmd /c cd /d。

工作目录：G:\\project_X
"""
brief_path = Path(r"G:\project_X\.hermes\issue15_handoff.md")
brief_path.write_text(brief, encoding="utf-8")

codex = shutil.which("codex")
env = os.environ.copy()
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
env["HTTP_PROXY"] = "http://127.0.0.1:7890"

prompt = ("读取 G:\\project_X\\.hermes\\issue15_handoff.md 并严格按其中任务执行，"
          "不要询问，直接完成全部工作后输出总结报告。")
r = subprocess.run(
    [codex, "exec", "--skip-git-repo-check", "--sandbox", "danger-full-access",
     "-m", "astra", prompt],
    cwd=r"G:\project_X", capture_output=True, text=True, timeout=550,
    errors="replace", env=env)
out = (r.stdout or "") + (r.stderr or "")
Path(r"G:\project_X\runtime\logs\astra_i15_handoff.log").write_text(out, encoding="utf-8")
print(f"exit={r.returncode}")
print(out[-1000:])
