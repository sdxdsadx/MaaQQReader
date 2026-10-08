"""第一轮成果丰富：3 个修复 commit + 4 个深度 findings。
派第二轮继续（更高难度主题：findings 里的 4 个问题逐一修复）。"""
import os
import shutil
import subprocess
from pathlib import Path

codex = shutil.which("codex")
env = os.environ.copy()
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
env["HTTP_PROXY"] = "http://127.0.0.1:7890"

brief = Path(r"D:\游戏文件\chatgpt\gameflow\.hermes\explore_round2.md")
brief.write_text("""# 任务：GameFlow 深度审查与修复（第 2 轮）——落实第 1 轮 findings

仓库 D:\\游戏文件\\chatgpt\\gameflow。第 1 轮产出 .hermes/findings-round1.md
（4 个深度 findings）与 3 个修复 commit。

## 本轮目标：逐条落实 findings-round1.md
1. **SqliteGameflowStore 跨表快照事务**：LoadCatalogAsync 加 deferred read
   transaction，同事务传给 LoadKindAsync；补确定性并发测试（可控暂停点，
   非概率压力测试）
2. **TaskExecutionCoordinator 不合作取消**：先读 ITaskExecutionRuntime 契约，
   设计迟到任务收口（迟到 runtime 仍被关闭、开始动作不再产生输入），
   补不合作实现测试
3. **ManagedProcessSession 线程安全**：按 finding 建议写入接口说明
   （单调用者约束注释），或实现异步门保护（选前者，最小改动）
4. **MuMu JsonDocument 泄漏**：修 Dispose/using，补测试

## 规则
- 每条独立 commit（fix(scope): 描述）
- 全量测试保持通过：cmd /c "dotnet test Gameflow.slnx -c Debug --filter Category!=RealIntegration"
- 完成后更新 findings-round1.md 标记已落实项
- 剩余额度继续第 2 轮扫描（UI 层例外）： Blazor 组件状态管理/Dispose 模式
- 不 push；git add 明确文件
- 结束输出总结报告
""", encoding="utf-8")

prompt = ("读取 D:\\游戏文件\\chatgpt\\gameflow\\.hermes\\explore_round2.md 并严格按其中任务执行，"
          "不要询问，用满本次会话时间完成全部落实与第二轮扫描，最后输出总结报告。")
r = subprocess.run(
    [codex, "exec", "--skip-git-repo-check", "--sandbox", "danger-full-access", prompt],
    cwd=r"D:\游戏文件\chatgpt\gameflow", capture_output=True, text=True, timeout=540,
    errors="replace", env=env)
out = (r.stdout or "") + (r.stderr or "")
Path(r"G:\project_X\runtime\logs\codex_gf_explore2.log").write_text(out, encoding="utf-8")
print(f"exit={r.returncode}")
print(out[-700:])
