# 接入 MFAAvalonia 作为 QQReader 日常 GUI —— 设计

日期：2026-10-06　分支：`claude/mfa-gui-20261006`

## 1. 目标与范围

**用户诉求**：MaaFramework 有官方通用 GUI，按 README「通用 UI」列表第一个（MFAAvalonia，<https://github.com/SweetSmellFox/MFAAvalonia>）重构 QQReader 的 GUI；测试通过后推送 GitHub 并发布新 Release。

**已确认的决定**

| 问题 | 决定 |
| --- | --- |
| 重构方式 | 直接接入 MFAAvalonia（PI V2 `interface.json` + Python Agent），不是仿写界面 |
| Agent 通信 | 使用官方 Python 绑定 `MaaFw`，版本对齐 `dev/` 下 MaaFramework v5.12.3 |
| 旧 Tkinter GUI | 保留代码与测试；`启动QQReaderGUI.cmd` 默认改开 MFA，带参数 `classic` 时打开旧 GUI |

**成功标准**

1. 在 MFAAvalonia 中勾选任务、设定分钟数后点开始，任务经现有 `scripts/run_task.py` 执行，界面显示每项成功或失败。
2. 1 分钟冒烟试跑（每日自动阅读 → 每日游戏 → 每日听书）三项成功，`runtime/records/daily_flows/` 有对应记录。
3. `py -3.10 -m pytest` 全量通过；已知的 master 原有失败不得增加。
4. 旧 GUI 仍能通过 `启动QQReaderGUI.cmd classic` 打开。

**不在范围内**：重写任何任务逻辑；在 MFA 中重做动态计划、截取封面、一键启动模拟器（这几项继续在旧 GUI 中使用）；验证码求解器（归 QQR-34）。

## 2. 结构

```
mfa/
  interface.json                   入库：PI V2 项目描述
  resource/pipeline/qqreader.json  入库：每个任务一个入口节点
  agent/main.py                    入库：AgentServer 入口（自检 + 注册动作）
  MFAAvalonia.exe 及其程序文件      不入库（.gitignore），按官方 Release 下载
qqreader/mfa/
  __init__.py
  agent_action.py                  纯逻辑：参数解析、命令构造、交接判定、子进程运行
```

### 2.1 interface.json

- 起点：旧工程 `_backup_old_project_20260909_200716/assets/interface.json`（只读参考，不修改原文件）。
- `controller`：一项 `Adb`，`display_short_side: 720`。
- `resource`：`./resource`。
- `agent`：`child_exec` 为 `python`，`child_args` 为 `["-X", "utf8", "./agent/main.py"]`。启动脚本把 PATH 中排在最前的 python 设成本机配置里的 Python 3.10。
- `task`：与 `qqreader/gui/task_catalog.DEFAULT_TASK_CATALOG` 中 `implemented=True` 的任务一一对应。`name` 使用目录中的中文名，`entry` 为 `QQR_<任务键>`，日常默认勾选的任务设 `default_check`。可多次执行的任务（自动阅读）用 MFA 扩展字段 `repeatable` / `repeat_count`。
- `option`：分钟数、超时分钟、最大步数、书名、封面路径做成 `input` 类型；“首本兜底”做成 `switch` 类型。均通过 `pipeline_override` 写入对应节点的 `custom_action_param`。默认值取任务目录中的默认值。

### 2.2 pipeline

每个任务一个节点，例如：

```json
"QQR_DailyReadingFlow": {
  "action": "Custom",
  "custom_action": "QQReaderRunTask",
  "custom_action_param": {"task": "DailyReadingFlow", "minutes": 35}
}
```

节点内不做识别，所有页面判断都留在 `run_task.py` 里。

### 2.3 Agent 动作 `QQReaderRunTask`

`agent/main.py` 只负责三件事：启动自检、把仓库根目录加入 `sys.path`、注册动作并 `AgentServer.start_up(socket_id)`。逻辑全部在 `qqreader/mfa/agent_action.py`：

1. `parse_param(raw)`：解析 `custom_action_param`，按 `TaskSpec.fields` 中各字段的 `normalize` 校验，未知任务键直接报错。
2. 定位本机配置 `configs/qqreader.local.json`。缺失时返回失败，并提示“请用 启动QQReaderGUI.cmd 启动”。
3. 交接检查：调用 `build_handoff_command(..., next_task=<任务键>)`。检查报告为验证码阻塞时，不执行任务，返回失败，日志写 `BLOCKED_BY_CAPTCHA / WAITING_FOR_HUMAN`。报告为“跳过”时同样返回失败并写明原因。
4. 运行任务：`build_run_task_command(...)` 启动子进程，逐行转发 stdout 到 agent 日志（MFA 会显示）。退出码为 0 时返回成功；非 0 时返回失败，原因用 `describe_exit_code` 说明。
5. 停止：轮询 `context.tasker.stopping`。为真时只结束本次启动的子进程（按 PID，Windows 下用 `taskkill /PID <pid> /T /F`），不按进程名批量结束。
6. 记录：每次动作把交接结果和任务结果写入 `runtime/records/daily_flows/mfa_<日期>_<id>.json`，复用 `DailyFlowRecorder`。

设备：MFA 用自己的 ADB 控制器连接，并显示截图。任务子进程按本机配置独立连接同一台 MuMu，与现在旧 GUI 的做法相同。

### 2.4 启动脚本

`启动QQReaderGUI.cmd` 第 1～4 步（定位 Python、查 ADB 端口、拉起模拟器、回写配置）不变。最后一步改为：

- 参数为 `classic` 时：按原方式启动 Tkinter GUI。
- 否则：检查 `mfa\MFAAvalonia.exe` 是否存在，不存在则打印下载说明后退出。存在时检查 `import maa`，失败则打印 `py -3.10 -m pip install "MaaFw==5.12.*"` 后退出。都通过后，把 Python 目录前置到 PATH、设好 PYTHONPATH，启动 MFA。

### 2.5 依赖

`pyproject.toml` 增加可选依赖 `mfa = ["MaaFw==5.12.*"]`。核心包仍然零依赖，测试不依赖 `maa`：`agent_action.py` 不导入 `maa`，只有 `mfa/agent/main.py` 导入。

## 3. 错误处理

| 情况 | 行为 |
| --- | --- |
| 未装 MaaFw 或版本不符 | `agent/main.py` 打印原因与修复命令后以非 0 退出；启动脚本预先检查 |
| 本机配置缺失 | 动作返回失败，提示用启动脚本 |
| 参数非法 | 界面端用 `verify` 正则拦截；agent 端再校验一次，失败返回失败 |
| 验证码 | 不执行任务、不返回、不重启 App，记 `BLOCKED_BY_CAPTCHA` |
| 子进程超时 | 由 `run_task.py` 自身超时处理，agent 只收尾 |
| 用户停止 | 只结束本次子进程 PID |

## 4. 测试

- `tests/test_mfa_interface.py`：
  - 每个任务都能在 `DEFAULT_TASK_CATALOG` 中找到；
  - 每个 `entry` 都有对应的 pipeline 节点；
  - 每个 `{占位符}` 都在 `inputs` 中定义；
  - 默认值与任务目录一致；
  - 每个选项都被至少一个任务引用。
- `tests/test_mfa_agent_action.py`：
  - 参数到命令行的转换；
  - 退出码映射为成功或失败；
  - 交接阻塞时不启动任务；
  - 停止时只结束自己的 PID；
  - 配置缺失时的提示。
- 全量 `py -3.10 -m pytest`。
- 实机：在 MFA 中做 1 分钟冒烟试跑（自动阅读 → 游戏 → 听书）；`启动QQReaderGUI.cmd classic` 打开旧 GUI。

## 5. 提交与发布

- 分支 `claude/mfa-gui-20261006`，CHANGELOG 条目与代码同一提交。
- 推送前自查：`git log --oneline github/master..HEAD`、diff 中无密钥、无大于 5 MB 的文件、测试通过。注意：本地 `master` 比 `github/master` 多 5 个未推送提交（QQR-53 弹窗修复等），推送 `master` 会一并发布。
- `--no-ff` 合并到 `master`，合并后重跑测试；打标签 `v2026.10.06-mfa-gui`，发布 GitHub Release。
- Release 不附带 MFAAvalonia 程序本体，说明里给出官方下载链接和安装步骤；附件为 `mfa/` 资源包 zip（`interface.json`、pipeline、agent）。
- 需用户逐项确认的外部操作：`pip install MaaFw`；下载 MFAAvalonia 官方包。
