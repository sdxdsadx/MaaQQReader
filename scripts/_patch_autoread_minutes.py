"""给 auto_read_30min.py 加 --minutes 参数（默认 30），支持短时长补差。"""
from pathlib import Path

p = Path(r"G:\project_X\scripts\auto_read_30min.py")
src = p.read_text(encoding="utf-8")
old = """def main() -> int:
    duration = 30 * 60"""
new = """def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=30)
    args, _ = ap.parse_known_args()
    duration = args.minutes * 60"""
assert old in src
src = src.replace(old, new)
src = src.replace('log("=== 自动阅读 30 分钟开始 ===")',
                  'log(f"=== 自动阅读 {args.minutes} 分钟开始 ===")')
src = src.replace('log("30 分钟到 → 关闭弹窗/返回")',
                  'log(f"{args.minutes} 分钟到 → 关闭弹窗/返回")')
src = src.replace('log("=== 自动阅读挂机完成 ===")',
                  'log("=== 自动阅读挂机完成 ===")')
# 弹窗检测文本 30 分钟硬编码 → 通用化
src = src.replace('if "已阅读30分钟" in t or "休息一下" in t:',
                  'if ("已阅读" in t and "分钟" in t) or "休息一下" in t:')
src = src.replace('if ("已阅读30分钟" in t) or ("休息一下" in t):',
                  'if ("已阅读" in t and "分钟" in t) or "休息一下" in t:')
p.write_text(src, encoding="utf-8")
print("auto_read 脚本支持 --minutes")
