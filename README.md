# QQReader

QQ 阅读每日任务自动化（MaaFramework 重构）的新仓库。

> 旧仓库 `G:\project_X` 只读；所有改动都发生在本仓库。

## 当前状态（2026-09-09）

已完成 **QQR-3「页面状态机与任务契约」**、**QQR-5「识别失败先确认与恢复」**、
**QQR-6「广告与游戏多特征识别策略」**、**QQR-10「运行结果状态、失败原因记录与关键节点截图」**
与 **QQR-17「奖励页游戏入口 / 去玩游戏按钮」** 的核心实现，并有单元测试覆盖：

| 层 | 模块 | 内容 |
| --- | --- | --- |
| 页面状态 | `qqreader/page/` | `PageState`（`HOME` + 规范要求的 8 个状态 + 游戏中间态 `GAME_ENTRY`）、多特征 `FeatureSpec`/`FeatureMatch`、§3.6 降级链（模板 A → 模板 B / OCR / 页面结构）、`RecognitionVerdict`（`CONFIRMED` / `TEMPORARY_MISMATCH` / `NOT_PRESENT`）、`PageObservation`、`PageStateRecognizer`、`FeatureKeys`、默认状态定义 |
| 任务契约 | `qqreader/contract/` | `TaskContract` 的 8 个字段、条件原语（`AllOf`/`AnyOf`/`NotCondition`/`StateIs`/`StateIn`/`FeatureMatches`/`predicate`）、`TaskOutcome`/`TaskResult`、`KeyNodeScreenshot`/`RecoveryStep` |
| 恢复 | `qqreader/recovery/` | 升级式恢复阶梯 `EscalationPolicy`（重新截图 → 重新判断 → 关弹窗 → 返回 → 重进入口 → 重启 App → 可选重启模拟器 → 放弃） |
| 验证码 | `qqreader/captcha/` | `ManualCaptchaGuard`（默认等待人工）、`VerifyingCaptchaGuard`（求解后必须重新观测确认消失） |
| 调度 | `qqreader/runner/` | `TaskRunner`（阶段推进 / 超时 / 取消 / UNKNOWN 只重判或恢复 / 验证码优先阻塞）、`PageConfirmer`（确认阶梯）、`FileRunRecorder`（JSON 运行记录 + 关键节点截图 + 默认 30 天保留）、`TaskRegistry`、`TaskDefinition` |
| 具体任务 | `qqreader/tasks/` | 声明式 `StateActionPlan` + `PlannedTaskAdapter`；广告 `DailyAdFlow`、游戏 `DailyGameFlow` 的契约与动作计划；奖励页游戏入口 OCR「玩游戏领赠币」/「去玩游戏」点击与滚动查找；`build_default_registry` |
| 运行时协议 | `qqreader/runtime/` | `Clock`/`CancellationToken`/`DeviceController`/`PageObserver`/`TaskAdapter`/`TaskContext`，真实 MaaFramework 实现将注入这些协议 |

## 运行测试

```powershell
py -3.10 -m pytest
```

当前结果：**130 个单元测试全部通过**（13 个测试文件）。核心包 `qqreader/` 不依赖任何第三方库，仅测试需要 `pytest`。

## 尚未验证（不要当成已完成）

- **MaaFramework 适配器仍在并行开发中**：工作区存在未提交的 `qqreader/maa` 适配代码；本次 QQR-17 真机验证使用了该工作区版本，但它尚未纳入本次提交，主线仓库仍以协议 + 测试假对象为准。
- **未完整跑通任何真实每日任务**：QQR-17 已在真机验证「奖励页 → 去玩游戏 → 页面变化」的入口点击链路，但游戏大厅/加载页识别与后续挂机仍未完成（见 QQR-13）。
- **模板、ROI、阈值、OCR 文案未重新校准**：`FeatureKeys` 与默认状态定义来自旧工程静态审计；QQR-6 已实现「主特征失效 → 模板 B / OCR / 结构特征降级」的代码路径与回归测试，但真实模板仍必须在 QQR-14 / QQR-15 中用当前设备截图重新标定后才能视为有效。
- **验证码自动求解未实现**：默认守卫是等待人工；`VerifyingCaptchaGuard` 只负责「求解后确认消失」。
- **GUI / 配置存储未实现**：`FileRunRecorder` 已提供 JSON 运行记录与关键节点截图能力，GUI 与配置装配待后续任务接入。
- 广告与游戏的超时/挂机时长是初始默认值（广告 45 分钟、游戏挂机 25 分钟、游戏超时 30 分钟），待 QQR-15~20 / QQR-37~39 确认。

## 设计约束（来自 `AGENTS.md`）

- 调度核心**不按任务名特判**：名字只是注册键，行为由契约 + 适配器配置决定。
- `UNKNOWN` 或检测到验证码时**绝不继续盲目点击**；识别失败只能重判或恢复，不能判「目标不存在 / 任务失败」。
- 超时是 `TIMEOUT`，取消是 `CANCELLED`，验证码阻塞是 `BLOCKED_BY_CAPTCHA`，都不是 `FAILED`；只有「恢复阶梯耗尽 + 独立超时」才 `FAILED`。
- 任务成功只以该任务的 `success_condition` 为准，不能把「点击过 / 等待过 / 没报错 / 回到奖励页」当作成功。
