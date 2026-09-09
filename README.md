# QQReader

QQ 阅读每日任务自动化（MaaFramework 重构）的新仓库。

> 旧仓库 `G:\project_X` 只读；所有改动都发生在本仓库。

## 当前状态（2026-09-09）

已完成 **QQR-3「页面状态机与任务契约」**、**QQR-5「识别失败先确认与恢复」**、
**QQR-6「广告与游戏多特征识别策略」**、**QQR-10「运行结果状态、失败原因记录与关键节点截图」**、
**QQR-17「奖励页游戏入口 / 去玩游戏按钮」**、**QQR-18「游戏挂机完整退出链路」**、
**QQR-19「去玩游戏识别/点击修复」**、**QQR-20「游戏大厅下划 → 在线玩 → 游戏中心 → 进入游戏」**、
**QQR-21「GUI 重构并接入运行脚本」**、**QQR-22「MAA GUI 风格任务分级 + 串行执行」**、
**QQR-23「迁移旧 GUI 任务列表与功能」** 与 **QQR-24「GUI 视觉重构」**
的核心实现，并有单元测试覆盖：

| 层 | 模块 | 内容 |
| --- | --- | --- |
| 页面状态 | `qqreader/page/` | `PageState`（`HOME` + 规范要求的 8 个状态 + `GAME_ENTRY` / `GAME_HALL` / `GAME_CENTER` / `GAME_MENU` / `GAME_EXIT_CONFIRM` 等游戏中间态）、多特征 `FeatureSpec`/`FeatureMatch`、§3.6 降级链（模板 A → 模板 B / OCR / 页面结构）、`RecognitionVerdict`（`CONFIRMED` / `TEMPORARY_MISMATCH` / `NOT_PRESENT`）、`PageObservation`、`PageStateRecognizer`、`FeatureKeys`、默认状态定义 |
| 任务契约 | `qqreader/contract/` | `TaskContract` 的 8 个字段、条件原语（`AllOf`/`AnyOf`/`NotCondition`/`StateIs`/`StateIn`/`FeatureMatches`/`predicate`）、`TaskOutcome`/`TaskResult`、`KeyNodeScreenshot`/`RecoveryStep` |
| 恢复 | `qqreader/recovery/` | 升级式恢复阶梯 `EscalationPolicy`（重新截图 → 重新判断 → 关弹窗 → 返回 → 重进入口 → 重启 App → 可选重启模拟器 → 放弃） |
| 验证码 | `qqreader/captcha/` | `ManualCaptchaGuard`（默认等待人工）、`VerifyingCaptchaGuard`（求解后必须重新观测确认消失） |
| 调度 | `qqreader/runner/` | `TaskRunner`（阶段推进 / 超时 / 取消 / UNKNOWN 只重判或恢复 / 验证码优先阻塞）、`PageConfirmer`（确认阶梯）、`FileRunRecorder`（JSON 运行记录 + 关键节点截图 + 默认 30 天保留）、`TaskRegistry`、`TaskDefinition` |
| 具体任务 | `qqreader/tasks/` | 声明式 `StateActionPlan` + `PlannedTaskAdapter`；广告 `DailyAdFlow`、游戏 `DailyGameFlow` 的契约与动作计划；HOME 使用书架 OCR「本周阅读时长」进奖励页、奖励页滚动查找「去玩游戏」并在 OCR 定位失败时退到按钮坐标 fallback；游戏大厅下划一次 → 识别「在线玩」→ 游戏中心点游戏卡「在线玩」→ 登录/协议页（勾选/登录游戏）→ `GAME_RUNNING`「领币」计时；退出流程含「退出」「关闭游戏」和返回奖励页，退出后禁止再次进入游戏；`build_default_registry` |
| 运行时协议 | `qqreader/runtime/` | `Clock`/`CancellationToken`/`DeviceController`/`PageObserver`/`TaskAdapter`/`TaskContext`；`qqreader/maa/` 已提供 MaaFramework ctypes 适配（截图/OCR/模板/点击/滑动/前台 App）；`scripts/run_task.py` 支持 `DailyGameFlow` / `DailyAdFlow` / `LaunchQQReader` / `SmokeTest`，旧任务明确输出未接入 |

## 运行测试

```powershell
py -3.10 -m pytest
```

当前结果：**170 个单元测试全部通过**（18 个测试文件）。核心包 `qqreader/` 不依赖任何第三方库，仅测试需要 `pytest`。

## GUI 控制台（MAA GUI 风格）

推荐直接双击仓库根目录的：

```text
启动QQReaderGUI.cmd
```

或：

```powershell
start-gui.cmd
# 等价于
py -3.10 -m qqreader.gui --config configs/qqreader.local.json
```

构建单文件 exe：

```powershell
build-gui-exe.cmd
# 产物：dist\QQReaderGUI.exe
```

`dist\QQReaderGUI.exe` 可直接双击；它会向上查找仓库根目录的 `scripts\run_task.py`，并使用配置里的 `machine.python_executable`（未配置时自动使用 `python` 或 `py -3.10`）来运行脚本。

GUI 已迁移旧 GUI 的全部任务列表（按旧顺序）：

```text
00 启动 QQ 阅读并关闭开屏弹窗
00 页面识别检查
01 每日自动阅读（默认 2 次 × 35 分钟）
02 每日听书（默认 35 分钟）
03 每日游戏（默认 25 分钟）
04 每日广告完整流程（自动至 12/12）
05 外部应用每日流程（大众点评 + 百度地图）
06 等级页广告每日流程（赠币 + 积分）
07 领取全部已完成奖励
```

其中 `DailyGameFlow`、`DailyAdFlow`、`LaunchQQReader`、`SmokeTest` 已接入新运行脚本；
其余旧 pipeline 任务保留在任务树中并标记「未接入」，运行时会明确输出
`[not-implemented]`，不会被当作成功。

GUI 支持：

- 视觉：浅灰背景 + 白色卡片；顶部标题/配置；工具条与底部操作栏分离；深色日志区按 `[observe]` / 成功 / 失败 / 未接入着色；状态点显示运行/停止/完成/失败；
- 左侧任务树：按分组展示任务，点击「启用」列勾选/取消；
- 右侧任务设置：每个任务独立设置重复次数、每次分钟、任务超时、最大步数；
- 「串行执行」按任务树顺序依次运行所有已启用任务，`count>1` 会自动展开重复执行；
- 「运行选中任务」只执行当前任务；
- 「每日默认」/「1分钟试运行」预设；
- 上移 / 下移调整任务顺序，并保存到 `runtime/gui_tasks.json`；
- 启动 MuMu 模拟器并自动执行 `adb connect`；
- 「启动QQ阅读」「识别检查」快捷按钮；
- 实时显示每个子进程的 `[observe]` OCR 日志、结果和诊断；
- 停止当前任务并终止整个串行队列；
- 打开配置中的 `record_dir`。

单任务命令行：

```powershell
py -3.10 scripts/run_task.py --config configs/qqreader.local.json `
  --task DailyGameFlow --duration-minutes 0.02 --timeout-minutes 3

py -3.10 scripts/run_task.py --config configs/qqreader.local.json `
  --task DailyAdFlow --timeout-minutes 5

py -3.10 scripts/run_task.py --config configs/qqreader.local.json `
  --task LaunchQQReader

py -3.10 scripts/run_task.py --config configs/qqreader.local.json `
  --task SmokeTest

# 旧任务会输出未接入
py -3.10 scripts/run_task.py --config configs/qqreader.local.json `
  --task DailyReadingFlow --minutes 35
```

## 真机运行游戏流程

```powershell
# 22 分钟正式挂机
py -3.10 scripts/run_game_flow.py --config configs/qqreader.local.json

# 短计时干跑（约 1.2 秒），用于验证入口/退出链路
py -3.10 scripts/run_game_flow.py --config configs/qqreader.local.json `
  --duration-minutes 0.02 --timeout-minutes 3
```

脚本会实时打印每次观测的 OCR/方向/App，任务结束时打印结果、原因和诊断；
运行记录与截图写入配置的 `record_dir` / `screenshot_dir`。

## 尚未验证（不要当成已完成）

- **MaaFramework 适配器已接入主线**：`qqreader/maa/` 与配置字段已提交；真机验证使用 `scripts/run_game_flow.py`，可实时观察每次 OCR 观测。
- **GUI 已接入新脚本**：`qqreader/gui/` + `gui/maa_qq_reader_gui.py` 已实现配置加载、启动模拟器、运行/停止 `scripts/run_game_flow.py` 和实时日志；提供 `启动QQReaderGUI.cmd` / `start-gui.cmd` 双击入口，并已用 `build-gui-exe.cmd` 构建 `dist\QQReaderGUI.exe` 验证可启动。
- **未完整跑通 22 分钟真实每日任务**：QQR-20 已在真机监督跑通「书架 HOME → 奖励页 → 去玩游戏 → 游戏大厅下划 → 在线玩 → 游戏中心点卡片 → 登录/协议 → 登录游戏 → 领币计时 → 退出/返回奖励页」；因当日游戏时长未满，奖励页显示「再玩 2 分钟即可领取」，尚未真机验证「立即领取」点击后的最终赠币到账。可再次执行 `scripts/run_game_flow.py` 等待时长满足后补验。
- **QQR-19 入口链路已真机验证**：书架 `HOME` → OCR「本周阅读时长」→ 奖励页顶部 → 滚动查找 → `GAME_ENTRY` → 点击「去玩游戏」→ 页面变化；OCR 定位失败时的按钮坐标 fallback 由单元测试覆盖。
- **模板、ROI、阈值、OCR 文案未重新校准**：`FeatureKeys` 与默认状态定义来自旧工程静态审计；QQR-6 已实现「主特征失效 → 模板 B / OCR / 结构特征降级」的代码路径与回归测试，但真实模板仍必须在 QQR-14 / QQR-15 中用当前设备截图重新标定后才能视为有效。
- **验证码自动求解未实现**：默认守卫是等待人工；`VerifyingCaptchaGuard` 只负责「求解后确认消失」。
- **GUI / 配置存储未实现**：`FileRunRecorder` 已提供 JSON 运行记录与关键节点截图能力，GUI 与配置装配待后续任务接入。
- 广告与游戏的超时/挂机时长是初始默认值（广告 45 分钟、游戏挂机 22 分钟、游戏超时 30 分钟），待 QQR-15~20 / QQR-37~39 确认。

## 设计约束（来自 `AGENTS.md`）

- 调度核心**不按任务名特判**：名字只是注册键，行为由契约 + 适配器配置决定。
- `UNKNOWN` 或检测到验证码时**绝不继续盲目点击**；识别失败只能重判或恢复，不能判「目标不存在 / 任务失败」。
- 超时是 `TIMEOUT`，取消是 `CANCELLED`，验证码阻塞是 `BLOCKED_BY_CAPTCHA`，都不是 `FAILED`；只有「恢复阶梯耗尽 + 独立超时」才 `FAILED`。
- 任务成功只以该任务的 `success_condition` 为准，不能把「点击过 / 等待过 / 没报错 / 回到奖励页」当作成功。
