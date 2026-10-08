"""🎉 重大突破：toast「已开启自动阅读」+ 面板标题变「自动阅读中·设置」！
自动阅读成功开启！（重启 app 清掉了挂死的人声朗读会话——根因确认）
翻页 False 是因为：自动阅读刚开启，第一屏停留可能 20s+（阅读速度设置），
28s 采样窗没赶上翻页——不碍事，看护循环 60s 间隔会正常跟踪。
现在直接启动 auto_read_30min.py：is_auto_reading 检测可能 False
（14s 窗口没翻页）→ 它会 toggle 关掉！风险！
改：脚本已带 is_auto_reading，但我直接跑——不行，先修 is_auto_reading
窗口 14s→22s？自动阅读默认速度约 20s+/屏。把 is_auto_reading 和看护
验证的间隔拉到 25s。"""
from pathlib import Path

p = Path(r"G:\project_X\scripts\auto_read_30min.py")
src = p.read_text(encoding="utf-8")
old = """def is_auto_reading() -> bool:
    \"\"\"12s 内正文首行变化 = 自动阅读进行中。\"\"\"
    l1 = body_first_line()
    time.sleep(12)
    l2 = body_first_line()
    return l1 != l2"""
new = """def is_auto_reading() -> bool:
    \"\"\"25s 内正文首行变化 = 自动阅读进行中（默认阅读速度约 20s+/屏）。\"\"\"
    l1 = body_first_line()
    time.sleep(25)
    l2 = body_first_line()
    return l1 != l2"""
assert old in src
src = src.replace(old, new)
old2 = """        cur = body_first_line()
        if cur == last_line:
            stall += 1"""
new2 = """        time.sleep(20)  # 自动阅读一屏约 20s+，60s+20s 采样窗内必有翻页
        cur = body_first_line()
        if cur == last_line:
            stall += 1"""
assert old2 in src
src = src.replace(old2, new2)
p.write_text(src, encoding="utf-8")
print("检测窗口 14s→25s，看护采样 +20s")
