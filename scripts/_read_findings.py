"""第一轮探索超时被 kill，但 codex 在 540 秒内已经完成 **3 个修复 commit**
（storage 事务校验 / domain 时序校验 / evidence 日志检测）+ findings 文档。
工作成果有效！python wrapper 超时只是没等到 codex 自然退出。
检查 findings 文档内容 + 测试是否全绿，然后派第二轮继续用额度。"""
import subprocess

r = subprocess.run(
    ["cmd", "/c", "type .hermes\\findings-round1.md 2>nul"],
    cwd=r"D:\游戏文件\chatgpt\gameflow", capture_output=True, text=True,
    timeout=20, errors="replace")
print((r.stdout or "无 findings 文件")[:1200])
