"""滑动翻页已生效：第39章 → 第42章（3 章推进），页面内容持续变化！
（日志行只在 taps%15==0 时打，属正常。）
280 分钟长跑预计 05:00 前后结束。滑动模式验证成功。
现在接力处理 Codex #15 的收尾：slide.py 已修（落盘未 commit），
nav.py 未写完。按用户规则换 astra 模型继续跑——但先确认用户说的
『astra』具体是哪个 CLI（本机装的是 codex/dsh/zcode/opencode/claude-code），
查看 dsh/zcode 配置里有没有 astra 模型。先查。"""
import subprocess

for tool in ("dsh", "zcode"):
    r = subprocess.run(["cmd", "/c", f"{tool} --help"], capture_output=True,
                       text=True, timeout=30, errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if "astra" in out.lower():
        print(f"{tool}: 提到 astra")
        for line in out.splitlines():
            if "astra" in line.lower():
                print(" ", line.strip()[:120])
    else:
        print(f"{tool}: 无 astra 字样")
