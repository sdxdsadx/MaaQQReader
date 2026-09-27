# 使用指南

日常运行、调试脚本、GUI 控制台与命令行的完整说明。

> 返回 [README](../README.md)

## 启动与调试脚本

**环境要求**

- Windows + MuMu 模拟器 12（实例 0）
- Python 3.10（`py -3.10` 或仓库内 `.venv`）
- MaaFramework 运行时（仓库 `dev/` 目录已附带 DLL、OCR 模型与资源）
- 可选：`opencv-python`、`numpy`（滑动验证码求解）；`pytest`（测试）

**第一次使用**

1. 复制 `configs/qqreader.example.json` 为 `configs/qqreader.local.json`，填写本机路径（见[配置说明](configuration.md)）。
2. 双击仓库根目录的 **`启动QQReaderGUI.cmd`**。
3. 在 GUI 中点击 **「一键执行今日任务」**。

仓库根目录只保留两个启动脚本：

| 脚本 | 用途 |
| --- | --- |
| **`启动QQReaderGUI.cmd`** | 日常使用：准备环境后打开 GUI |
| **`调试QQReader.cmd`** | 排障/调试：冷启动、环境体检、识别检查、单任务运行、单元测试、冷停止 |

`启动QQReaderGUI.cmd` 会依次：

1. 定位 Python 3.10（配置里的 `machine.python_executable` → `.venv` → `py -3.10` → `python`）；
2. 通过 MuMuManager 查询实例的真实 ADB 端口（不写死端口）；
3. 模拟器未运行时自动拉起，并等待 ADB 可连接、系统启动完成；
4. 把端口回写到 `configs/qqreader.local.json` 的 `adb_address`；
5. 设置 `PYTHONPATH` 后启动 GUI。

环境异常（adb offline、端口漂移、模拟器卡死）或需要调试时，使用 **`调试QQReader.cmd`**。双击会弹出菜单：

```text
1. 环境体检（不做任何变更）
2. 冷启动环境 + 打开 GUI
3. 彻底重启模拟器（/cold）+ 打开 GUI
4. 冷启动环境 + 页面识别检查（SmokeTest）
5. 冷启动环境 + 单独运行一个任务（询问任务名与分钟数）
6. 运行单元测试
7. 冷停止（关 GUI + 关模拟器 + 清 adb）
```

也可以从命令行带参数调用：

```text
调试QQReader.cmd [gui|run|smoke|task|test|stop|status] [/cold] [/force]

gui      冷启动环境后打开 GUI（默认）
run      冷启动环境后直接跑每日全链路
smoke    冷启动环境后做页面识别检查
task     冷启动环境后单独运行一个任务
test     只跑单元测试
stop     冷停止：关 GUI + 关模拟器 + 清 adb
status   只体检环境，不做任何变更
/cold    彻底重启模拟器（先关机再开机）
/force   忽略“已有任务在跑”的保护
```

冷启动与普通启动的区别：会先 `adb kill-server` 清掉残留/离线设备；运行中的任务会被保护，不会被打断（除非加 `/force`）。

## GUI 控制台

```powershell
py -3.10 -m qqreader.gui --config configs/qqreader.local.json
# 兼容旧入口
py -3.10 gui/maa_qq_reader_gui.py --config configs/qqreader.local.json
```

### 界面布局

```text
┌──────────┬──────────────────────────────────────────────────────────────┐
│ 侧边栏    │ 今天的任务：已选 N 项 · 实际执行 M 步 · 计时约 X 分钟   [● 状态] │
│          │ （可折叠）本机设置：配置文件 / 任务间隔 / 保存                   │
│ 快速选择  ├──────────────┬─────────────────┬─────────────────────────────┤
│ 环境与工具 │ 任务队列      │ 任务详情         │ 运行日志                     │
│          │ 勾选/排序     │ 参数编辑/单独运行 │ 实时输出，按类型着色          │
│          │              ├─────────────────┤                             │
│ 本机配置  │              │ 执行计划/本轮进度 │                             │
│ 状态      ├──────────────┴─────────────────┴─────────────────────────────┤
│          │ 当前任务 · 已用时间 · 进度条   [直接运行已选][一键执行今日任务][停止] │
└──────────┴──────────────────────────────────────────────────────────────┘
```

| 区域 | 说明 |
| --- | --- |
| **侧边栏 · 快速选择** | `选择今日流程`（阅读→听书→游戏→奖励页广告→等级广告，恢复正式时长）、`选择1分钟试跑`（阅读/听书/游戏各 1 分钟）、`每周阅读600分钟`（仅阅读，10 次 × 35 分钟）、`动态规划`（读取奖励页剩余任务并自动勾选，按剩余时长加 5 分钟缓冲）、`全不选` |
| **侧边栏 · 环境与工具** | `仅启动环境`（模拟器 → ADB 就绪 → 启动 QQ 阅读并清理开屏弹窗）、`启动QQ阅读`、`识别检查`（截图并输出当前页面状态/OCR）、`运行记录`（打开 `record_dir`）、`设置`（展开/收起本机设置） |
| **侧边栏底部** | 本机配置加载状态：✓ 已加载 / ✗ 加载失败 / 未加载 |
| **任务队列** | 每行包含序号、勾选、任务名、参数摘要（如 `2 次 × 35 分钟 · 超时 50 分钟`）和 ▲▼ 排序；点击某行在右侧查看详情 |
| **任务详情** | 编辑重复次数、每次分钟、挂机分钟、超时等参数，旁边标注单位和取值范围，超出范围时显示红字提示；`单独运行此任务` 只跑当前任务 |
| **执行计划 / 本轮进度** | 空闲时预览展开后的串行步骤（`count>1` 会拆成多步）；运行时显示每步状态（等待 / 运行中 / 成功 / 失败(exit code) / 验证码阻塞 / 已取消 / 跳过）和耗时 |
| **运行日志** | 子进程实时输出；`[observe]` 蓝色、成功绿色、失败红色、旧流程黄色；可关闭自动滚动；最多保留 5000 行 |
| **底部操作栏** | 当前任务与本轮已用时间、进度条；`直接运行已选`（主按钮）、`一键执行今日任务`、`停止当前任务` |

### 两个主按钮的区别

- **一键执行今日任务**：先恢复「今日流程」预设 → 启动模拟器 → 等待 ADB → 启动 QQ 阅读并清理弹窗 → 按队列串行执行。适合每天的无人值守运行。
- **直接运行已选**：不做环境准备，按当前队列里的勾选和参数直接开始。适合环境已就绪、调试或只补跑部分任务。

### 执行语义

- 队列从上到下**严格串行**；两项之间按「任务间隔」（默认 3 秒）等待，然后做**交接检查**：确认已回到书架才启动下一项（会依次处理确认框、广告挽留弹窗、书城页，其余页面按返回，必要时重启一次 App）。
  - 交接检查确认不了书架：下一项记为「跳过」，原因写入串行记录，再给后一项做交接检查。前项失败但现场已确认安全时照常继续。
  - 任务结束时处于验证码（退出码 10），或交接检查发现验证码：不点击、不返回、不重启，后续任务全部跳过，本轮状态为「验证码阻塞」，等待人工处理。
  - 退出码：0 成功 / 2 任务未成功 / 3 致命错误 / 10 验证码阻塞 / 11 超时 / 12 设备错误 / 13 取消 / 20 交接失败（定义见 `qqreader/runner/exit_codes.py`）。
- 开始时冻结本轮顺序和参数并生成 run id；每次状态变化都原子写入 `record_dir/daily_flows/<run-id>.json`，按北京时间 04:00 划分业务日。
- 点击停止后，当前项记为 `CANCELLED`，后续项记为 `SKIPPED`；本轮结果分为全部成功 / 完成但有错误 / 已停止。
- 运行中关闭窗口会先弹窗确认，确认后终止子进程再退出，不会留下后台任务。
- 勾选、参数和顺序修改后立即保存到 `runtime/gui_tasks.json`。

### 快捷键

| 按键 | 作用 |
| --- | --- |
| `F5` | 直接运行已选 |
| `Ctrl+S` | 保存任务设置 |
| `Ctrl+L` | 清空日志 |

## 命令行

所有任务都通过 `scripts/run_task.py` 执行，GUI 在后台调用的也是它。

```powershell
# 单个任务
py -3.10 scripts/run_task.py --config configs/qqreader.local.json --task LaunchQQReader
py -3.10 scripts/run_task.py --config configs/qqreader.local.json --task SmokeTest
py -3.10 scripts/run_task.py --config configs/qqreader.local.json --task DailyReadingFlow --minutes 35
py -3.10 scripts/run_task.py --config configs/qqreader.local.json --task DailyAdFlow --timeout-minutes 45
py -3.10 scripts/run_task.py --config configs/qqreader.local.json `
  --task DailyGameFlow --duration-minutes 0.02 --timeout-minutes 3

# 完整每日流水线（与 GUI 相同的流水线状态与记录语义）
py -3.10 scripts/daily_all.py
#   可选：--skip-reading / --skip-audiobook / --skip-game / --skip-ad / --game-minutes N

# 读取奖励页并生成动态计划（写入 runtime/gui_tasks.json）
py -3.10 scripts/dynamic_plan.py --config configs/qqreader.local.json

# 游戏流程真机调试：实时打印每次观测的 OCR/方向/前台 App
py -3.10 scripts/run_game_flow.py --config configs/qqreader.local.json
py -3.10 scripts/run_game_flow.py --config configs/qqreader.local.json `
  --duration-minutes 0.02 --timeout-minutes 3
```

`run_task.py` 支持的参数：`--task`、`--minutes`、`--duration-minutes`、`--timeout-minutes`、`--max-steps`、`--quiet`。
