"""issue #16 终修: 求解器改用 sendevent 拟人触摸流。
活体实验（live_sendevent.py）实证: 通过。
将成功逻辑封装进 SlideCaptchaSolver._humanize_swipe。
"""
from pathlib import Path

p = Path(r"G:\project_X\qqreader\captcha\slide.py")
src = p.read_text(encoding="utf-8")

old = '''    def _humanize_swipe(self, sx: int, sy: int, tx: int, ty: int, distance: int) -> None:
        """拟人滑动：分段轨迹 + 过冲回正 + 轻微抖动 + 随机时长。

        r2 实测：匀速直线 600ms 滑动两次都被行为检测拒绝（滑了 206px 仍判
        失败）。改为先快后慢的分段 swipe：主段快速接近（含 3~8px 随机过冲），
        停顿一拍后微调回正；纵向抖动 ±2px 模拟手指不稳。
        """
        base = max(350, min(900, int(distance * 2.2)))
        duration = base + random.randint(-60, 120)
        overshoot = random.randint(3, 8)
        jx = random.randint(-2, 2)
        jy = random.randint(-2, 2)
        # 主段：快速滑到目标 + 过冲
        self._device.swipe(sx, sy, tx + overshoot, ty + jy, duration)
        time.sleep(random.uniform(0.08, 0.18))
        # 回正段：慢速小幅拉回，像人手对齐拼图
        self._device.swipe(
            tx + overshoot, ty + jy, tx + random.randint(-1, 1), ty, random.randint(180, 320)
        )'''

new = '''    def _humanize_swipe(self, sx: int, sy: int, tx: int, ty: int, distance: int) -> None:
        """拟人滑动：sendevent 原始触摸流（变速 + 抖动 + 过冲回调）。

        活体实验（runtime/logs live_sendevent，2026-09-11）实证：MAA/adb
        input swipe 的匀速直线轨迹被行为指纹识别拒绝（回弹）；sendevent
        注入「ease-out 变速 + y 抖动 + 过冲微回调」原始事件流一次通过。
        dx = tx - sx 为目标位移。
        """
        dx = tx - sx
        dy = ty - sy
        track = self._human_track(dx)
        self._sendevent_track(sx, sy, track, dy)'''
assert old in src, "old block not found"
src = src.replace(old, new)

# 添加辅助方法（插在 _humanize_swipe 之后、solve 之前）
anchor = '''    def solve(self, context: "TaskContext") -> SolveResult:'''
helpers = '''    def _adb_shell(self, config: Any, script: str) -> None:
        import subprocess

        subprocess.run(
            [config.machine.adb_path, "-s", config.machine.adb_address,
             "shell", script],
            capture_output=True, timeout=20,
        )

    def _human_track(self, dx: int) -> list:
        """ease-out 变速轨迹: [(x_offset, dt_ms), ...]，含过冲与回调。"""
        pts = []
        over = random.randint(4, 9) * (1 if dx > 0 else -1)
        n = max(12, min(40, abs(dx) // 6))
        for i in range(1, n + 1):
            f = i / n
            ease = 1 - (1 - f) ** 2
            dt = random.randint(14, 34)
            pts.append((int(dx * ease) - int(dx * (1 - (i - 1) / n) ** 2) * 0, dt))
        # 上面的 ease 序列直接用绝对位置更稳，重新生成:
        pts = []
        prev = 0
        for i in range(1, n + 1):
            f = i / n
            ease = 1 - (1 - f) ** 2
            x = int(dx * ease)
            pts.append((x - prev, random.randint(14, 34)))
            prev = x
        pts.append((over, random.randint(20, 40)))
        pts.append((-over, random.randint(25, 50)))
        return pts

    def _sendevent_track(self, sx: int, sy: int, track: list, dy: int) -> None:
        from ..config import load_config  # 局部导入避免循环

        config = load_config("configs/qqreader.local.json")
        adb = config.machine.adb_path
        dev = config.machine.adb_address

        import subprocess

        r = subprocess.run(
            [adb, "-s", dev, "shell", "getevent", "-pl"],
            capture_output=True, text=True, timeout=20,
        )
        tdev = None
        cur = None
        for line in r.stdout.splitlines():
            m = re.search(r"add device \\d+: (/dev/input/event\\d+)", line)
            if m:
                cur = m.group(1)
            if cur and "ABS_MT_POSITION_X" in line:
                tdev = cur
                break
        if not tdev:
            # 无触屏设备：退化为设备 swipe（可能被行为检测拒绝）
            self._device.swipe(sx, sy, sx + sum(d for d, _ in track), sy,
                               self._swipe_duration_ms)
            return

        def send(events):
            script = "".join(f"sendevent {tdev} {t} {c} {v}; " for t, c, v in events)
            subprocess.run([adb, "-s", dev, "shell", script],
                           capture_output=True, timeout=20)

        x = sx
        y = sy
        send([(3, 57, 0), (3, 53, x), (3, 54, y), (1, 330, 1), (0, 0, 0)])
        time.sleep(0.05)
        for ddx, dt in track:
            x += ddx
            y = sy + random.randint(-2, 2)
            send([(3, 53, x), (3, 54, y), (0, 0, 0)])
            time.sleep(dt / 1000.0)
        time.sleep(random.uniform(0.08, 0.2))
        send([(3, 57, -1), (1, 330, 0), (0, 0, 0)])

'''
assert anchor in src
src = src.replace(anchor, helpers + anchor)
src = src.replace("import random\nimport tempfile", "import random\nimport re\nimport tempfile")
p.write_text(src, encoding="utf-8")
print("patched slide.py")
