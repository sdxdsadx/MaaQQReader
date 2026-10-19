"""Package the current application, sources and Maa runtime for GitHub Releases."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "QQReader-2026.09.23-windows"


def main():
    files = {}
    def add(path):
        path = ROOT / path
        if path.is_file():
            files[path.relative_to(ROOT).as_posix()] = path.read_bytes()

    for folder in ("qqreader", "gui", "tests", "docs"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                add(path)
    for name in ("README.md", "CHANGELOG.md", "pyproject.toml",
                 "启动QQReaderGUI.cmd", "调试QQReader.cmd",
                 "scripts/build-gui-exe.cmd"):
        add(name)
    for name in ("run_task.py", "auto_read_30min.py", "daily_all.py",
                 "dynamic_plan.py", "run_game_flow.py", "package_release.py"):
        add(Path("scripts") / name)
    for path in (ROOT / "dev").rglob("*"):
        rel = path.relative_to(ROOT / "dev")
        if path.is_file() and rel.parts[0] not in ("debug", "config"):
            add(path)
    legacy = Path("_backup_old_project_20260909_200716")
    add(legacy / "tools/run_maa_ad.py")
    add(legacy / "LICENSE")
    files["QQReaderGUI.exe"] = (ROOT / "dist/QQReaderGUI.exe").read_bytes()
    config = json.loads((ROOT / "configs/qqreader.example.json").read_text(encoding="utf-8"))
    machine = config["machine"]
    machine.update(adb_path="D:/Program Files/Netease/MuMu Player 12/shell/adb.exe",
                   emulator_path="D:/Program Files/Netease/MuMu Player 12/shell/MuMuManager.exe",
                   python_executable="D:/python/python.exe", screenshot_dir="../runtime/screenshots",
                   log_dir="../runtime/logs", record_dir="../runtime/records",
                   maa_runtime_dir="../dev", maa_resource_dir="../dev/resource",
                   maa_agent_dir="../dev/MaaAgentBinary")
    config["captcha"]["solver"] = "slide"
    files["configs/qqreader.local.json"] = (json.dumps(config, ensure_ascii=False, indent=2)+"\n").encode("utf-8")
    add("configs/qqreader.example.json")
    files["使用说明.txt"] = """QQReader 2026.09.23 Windows 发布包

完整解压后运行 启动QQReaderGUI.cmd 或 QQReaderGUI.exe。
需要 Windows、Python 3.10（含 tkinter）、MuMu 12，以及已登录的 QQ 阅读。
外部 Python 需要安装 numpy、opencv-python：python -m pip install numpy opencv-python
配置 configs/qqreader.local.json 中的 Python 和模拟器安装路径。
启动脚本的 MUMU_DIR 默认 D:\\Program Files\\Netease\\MuMu Player 12\\shell；其他安装位置请同步修改。
运行目录采用相对路径，可移动整个解压目录。GUI exe 仍需要包内源码和外部 Python 执行任务。
保留历史滑块模块，检测到验证码时自动调用；验证消失后继续新版流程。
视频广告默认等待 35 秒。启动脚本使用 UTF-8（无 BOM）和 CRLF。

本包是当前工作目录的应用快照，包含源码、测试、Maa DLL/OCR 模型和旧任务所需 runner。
不包含用户运行日志、截图、个人任务记录、开发代理配置或临时调试脚本。
验证：广告 GUI 实跑成功；启动脚本中文输出正常；GUI 已重新构建。
""".encode("utf-8")
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
    files["MANIFEST.sha256.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    output = ROOT / "dist" / (NAME + ".zip")
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(NAME + "/" + name, data)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(digest+"  "+output.name+"\n", encoding="ascii")
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
    print(f"{output}\n{len(files)} files, {output.stat().st_size} bytes\nSHA256 {digest}")


if __name__ == "__main__":
    main()
