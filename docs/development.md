# 开发、测试与构建

运行测试、打包 exe，以及参与开发前需要知道的规则。

> 返回 [README](../README.md)

## 测试与构建

```powershell
# 全部测试（核心包 qqreader/ 不依赖第三方库）
py -3.10 -m pytest

# 只跑 GUI 相关测试
py -3.10 -m pytest tests/test_gui_user_click_flow.py tests/test_gui_task_catalog.py tests/test_gui_commands.py
```

构建单文件 exe（需要 PyInstaller）：

```powershell
scripts\build-gui-exe.cmd
# 产物：dist\QQReaderGUI.exe
```

exe 需放在仓库根目录（或其子目录）中运行：它会向上查找 `scripts\run_task.py`，并用本机 Python（`machine.python_executable`，未配置时依次尝试 `python`、`py -3.10`）加载当前源码执行任务。

## 参与开发

- 开工前先读 [`AGENTS.md`](../AGENTS.md)（开发环境、领域规则、Git 规范）和 [`CHANGELOG.md`](../CHANGELOG.md) 最上方 3 条。
- 每次改动都要在 `CHANGELOG.md` 最上方追加一条记录，与代码放在同一个提交里。
- 不在 `master` 上直接提交；分支命名 `<agent>/<主题>-<YYYYMMDD>`。
- Issue 统一记录在 Linear 项目 MAAQQReader（编号 `QQR-xx`）。
