# 配置说明

本机配置文件 `configs/qqreader.local.json` 的字段说明。

> 返回 [README](../README.md)

## 配置

本机配置位于 `configs/qqreader.local.json`（模板：`configs/qqreader.example.json` / `.yaml`）。

| 字段 | 说明 |
| --- | --- |
| `machine.adb_path` / `adb_address` | ADB 可执行文件与设备地址（启动脚本会自动回写端口） |
| `machine.emulator_path` | MuMuManager.exe 或 MuMuPlayer.exe；GUI 据此启动模拟器 |
| `machine.package_name` | 默认 `com.qq.reader` |
| `machine.python_executable` | GUI 与 exe 调用脚本时使用的 Python；留空则自动查找 |
| `machine.record_dir` / `screenshot_dir` / `log_dir` | 运行记录、关键节点截图、日志目录（默认 `runtime/` 下） |
| `machine.maa_runtime_dir` / `maa_resource_dir` / `maa_agent_dir` | MaaFramework 运行时、资源和 Agent 目录 |
| `captcha.solver` | 验证码处理方式（`manual` 等），另有 `max_attempts`、`verify_frames` 等 |
| `tasks.<Task>` | 各任务的 `enabled`、`timeout_seconds`、`retry`、`feature_overrides` |

GUI 自身的任务勾选、次数、时长与顺序保存在 `runtime/gui_tasks.json`，与本机配置分开。
