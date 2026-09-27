# Codex 旧版 QQ 阅读脚本（2026-07-22）

这些文件从 `C:\Users\26142\Documents\Codex\2026-07-22\github-plugin-github-openai-curated-remote-5\outputs` 原样复制，用于保留早期实现和识别图片。迁移时逐文件比对了 SHA-256；不把这套脚本加入当前任务目录或日常启动链路。

**当前唯一维护和运行目录：`G:\project_X`。** 日常使用仓库根目录的 `启动QQReaderGUI.cmd`，调试使用 `调试QQReader.cmd`；后续 QQ 阅读自动化的代码、配置、文档和运行记录均在这个仓库维护。

| 旧版内容 | G 盘现行位置或处理 |
| --- | --- |
| `qqreader_automation.py` 的阅读、听书、游戏流程 | `qqreader/`、`scripts/run_task.py` 和现行 GUI；旧脚本仅供参考 |
| `qqreader_gui.py`、`task_modules/` 的任务顺序、次数、分钟数和间隔 | `qqreader/gui/`，本机设置保存在 `runtime/gui_tasks.json` |
| `templates/` 的八张识别图 | 原样保存在本目录；当前识别资源须按现行设备重新验证，未直接启用这些旧图 |
| 三个旧启动文件 | 原件保存在本目录；Codex 原位置的三个启动文件及两个 Python 入口已转向 G 盘 GUI |
| `自动点击日志.txt`、`最后画面.png` | `runtime/legacy/codex-2026-07-22/`，随本机运行资料保存，不进入 Git |
| `QQ阅读自动任务_模块流程修改模板.docx` | 原样保存在本目录作为历史资料 |

旧脚本使用固定的 MuMu/ADB 路径、固定书籍封面和坐标，且不包含现行工程的验证码状态、任务结果与恢复机制。需要借用其中逻辑或模板时，先在现行工程验证，再修改现行实现；不要把两套入口并行运行。
