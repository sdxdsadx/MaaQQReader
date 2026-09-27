# 架构与设计约束

代码目录结构，以及调度核心必须遵守的设计约束。

> 返回 [README](../README.md)

## 项目结构

```text
qqreader/
  gui/          GUI：app.py（窗口与交互）、theme.py（配色/样式）、widgets.py（卡片/任务行）、
                task_catalog.py（任务目录与串行计划，纯逻辑）、commands.py（子进程命令构造）、
                dynamic_plan.py（奖励页动态规划）
  page/         页面状态机：PageState、多特征识别与降级链、RecognitionVerdict
  contract/     任务契约：TaskContract、条件原语、TaskOutcome/TaskResult
  recovery/     升级式恢复阶梯（重截图 → 重判断 → 关弹窗 → 返回 → 重进入口 → 重启 App → …）
  captcha/      验证码检测、求解与复核
  runner/       TaskRunner（超时/取消/验证码阻塞）、PageConfirmer、运行记录
  runtime/      Clock / CancellationToken / DeviceController 等运行时协议
  maa/          MaaFramework ctypes 适配（截图/OCR/模板/点击/滑动）与 ADB 预检
  reward/       奖励页导航
  tasks/        具体任务：阅读、听书、游戏、广告、等级广告等
  workflow.py   每日流水线：冻结参数、业务日、串行状态与 JSON 记录
  config/       配置加载与校验
scripts/        run_task.py、daily_all.py、dynamic_plan.py、run_game_flow.py 及调试脚本
gui/            兼容旧入口 maa_qq_reader_gui.py（PyInstaller 打包入口）
configs/        配置模板与本机配置
dev/            MaaFramework 运行时、OCR 模型、pipeline 与调试产物
tests/          pytest 单元测试
docs/           使用/配置/架构文档、问题修复记录与历史档案
runtime/        运行时数据：gui_tasks.json、记录、截图、日志
```

## 设计约束

来自 [`AGENTS.md`](../AGENTS.md)：

- 调度核心**不按任务名特判**：任务名只是注册键，行为由契约和适配器配置决定。
- 页面为 `UNKNOWN` 或检测到验证码时**绝不盲目点击**；识别失败只能重新判断或恢复，不能据此判定「目标不存在」或「任务失败」。
- 超时是 `TIMEOUT`，取消是 `CANCELLED`，验证码阻塞是 `BLOCKED_BY_CAPTCHA`，都不是 `FAILED`；只有「恢复阶梯耗尽 + 独立超时」才判 `FAILED`。
- 任务成功只以该任务的 `success_condition` 为准；点击过、等待过、没报错或回到奖励页，都不能算成功。
