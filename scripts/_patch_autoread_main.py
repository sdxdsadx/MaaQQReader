"""设置面板 OCR 看不出开关态（无高亮文字差异）。最稳策略：
**toggle 后验证翻页，失败再 toggle 回来**——幂等重启法：
toggle → 等 10s 查翻页 → 若无翻页（说明原来开着，现在被关了）→ 再 toggle
恢复 + 再验证。
重写 auto_read_30min.py 主循环：
- 领先检测：先测 12s 首行是否在变（当前状态机）。
  在变 → 直接看护；不变 → toggle + 验证。"""
from pathlib import Path

p = Path(r"G:\project_X\scripts\auto_read_30min.py")
src = p.read_text(encoding="utf-8")

old = """def main() -> int:
    duration = 30 * 60
    log("=== 自动阅读 30 分钟开始 ===")
    if not enable_auto_read():
        # 再试一次
        if not enable_auto_read():
            log("❌ 自动阅读无法开启（两次尝试均无翻页）")
            return 2"""
new = """def is_auto_reading() -> bool:
    \"\"\"12s 内正文首行变化 = 自动阅读进行中。\"\"\"
    l1 = body_first_line()
    time.sleep(12)
    l2 = body_first_line()
    return l1 != l2


def main() -> int:
    duration = 30 * 60
    log("=== 自动阅读 30 分钟开始 ===")
    if is_auto_reading():
        log("已在自动阅读中 → 直接看护")
    elif not enable_auto_read():
        # toggle 可能把原本开着的关了：再 toggle 一次并验证
        if not enable_auto_read():
            log("❌ 自动阅读无法开启（两次尝试均无翻页）")
            return 2"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("主循环已改幂等检测")
