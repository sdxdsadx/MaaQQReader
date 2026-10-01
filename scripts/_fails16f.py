"""直接解析 trx/标准 xUnit 输出找失败对（用例→错误）。"""
import re

log = open(r"G:\project_X\runtime\logs\gf_test16.log", encoding="utf-8", errors="replace").read()
# xUnit v3 输出格式： [FAIL] TestName ...\r\n 错误消息: \r\n <msg>
pat = re.compile(r"\[FAIL\]\s+([A-Za-z0-9_.]+)\s*\r?\n(?:.*?\r?\n)*?\s*错误消息:\s*\r?\n\s*([^\r\n]+)", re.S)
for name, msg in pat.findall(log):
    print(name.split(".")[-1], "=>", msg.strip()[:130])
    print()
