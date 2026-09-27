<div align="center">

# QQReader

**QQ 阅读每日任务自动化**

每天自动完成阅读、听书、游戏挂机、看广告领币——打开 GUI，点一下，然后去做别的事。

![Platform](https://img.shields.io/badge/platform-Windows-0078D6)
![Python](https://img.shields.io/badge/python-3.10-3776AB)
![Framework](https://img.shields.io/badge/based%20on-MaaFramework-orange)
![Status](https://img.shields.io/badge/status-开发中-yellow)

[快速开始](#快速开始) · [使用指南](docs/usage.md) · [任务说明](docs/tasks.md) · [更新日志](CHANGELOG.md)

</div>

---

## 它能做什么

| 任务 | 内容 |
| --- | --- |
| 📖 每日阅读 | 自动翻页阅读（默认 2 × 35 分钟），结束后领取阅读奖励；只读[白名单书目](#书目白名单) |
| 🎧 每日听书 | 挂机听书《全职法师》35 分钟，关闭悬浮框并领取赠币（[书目说明](#书目白名单)） |
| 🎮 每日游戏 | 从奖励页进入游戏中心，登录、挂机领币、完整退出 |
| 📺 奖励页广告 | 循环观看视频广告，目标 12/12 |
| ⭐ 等级页广告 | 「我的 → 等级」里的赠币广告与积分广告 |

此外还有：

- **桌面 GUI 控制台**：勾选任务、调整次数和时长、查看实时日志与每步进度。
- **一键无人值守**：自动启动 MuMu 模拟器、连接 ADB、打开 QQ 阅读并清理弹窗，然后按顺序跑完所有任务。
- **动态规划**：读取奖励页的剩余任务，只勾选还没完成的部分。
- **稳健的执行方式**：识别不到页面时先确认、再按恢复阶梯处理，不盲点；遇到滑动验证码会尝试求解，失败则停下等人处理。
- **运行记录**：每一轮的结果、失败原因和关键截图都写入 `runtime/`，方便回查。

## 项目状态

> ⚠️ 仍在开发中，个人自用。请先用「1 分钟试跑」确认在你的环境下能正常工作。

| 能力 | 状态 |
| --- | --- |
| 阅读 / 听书 / 游戏（1 分钟试跑） | ✅ 真机通过（2026-09-27） |
| 游戏入口 → 挂机 → 退出整条链路 | ✅ 真机通过；赠币到账尚未确认 |
| 奖励页广告 12/12 | 🚧 未验收 |
| 连续 3 天无人值守 | 🚧 未验收 |
| 滑动验证码自动求解 | 🚧 可能阻塞广告计数（QQR-34） |

其他限制：模板、ROI 与 OCR 文案仍需按当前设备重新标定；听书任务暂时依赖旧工程目录 `_backup_old_project_20260909_200716/`；GitHub 仓库不含 `dev/`（MaaFramework 运行时）和旧工程目录，克隆后不能直接运行。详见 [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md)。

## 快速开始

**环境要求**：Windows · [MuMu 模拟器 12](https://mumu.163.com/)（实例 0，720×1280）· Python 3.10 · MaaFramework 运行时（本地 `dev/` 目录）

1. 复制 `configs/qqreader.example.json` 为 `configs/qqreader.local.json`，填入本机的 ADB、MuMu 与 Python 路径（[字段说明](docs/configuration.md)）。
2. 在 QQ 阅读里把《宇智波：从扉间人柱力开始》（自动阅读）和《全职法师》（听书）**加入书架**，否则阅读会直接失败、听书可能听错书（见下方[书目白名单](#书目白名单)）。
3. 双击根目录的 **`启动QQReaderGUI.cmd`**，它会自动启动模拟器、探测 ADB 端口并打开 GUI。
4. 首次使用先点侧栏的 **「选择1分钟试跑」→「直接运行已选」**；三项都显示成功后，日常点 **「一键执行今日任务」** 即可。

遇到 adb offline、端口漂移、模拟器卡死等问题，双击 **`调试QQReader.cmd`**，菜单里有环境体检、冷重启、识别检查和单任务运行。

更喜欢命令行？

```powershell
py -3.10 scripts/run_task.py --config configs/qqreader.local.json --task DailyReadingFlow --minutes 35
py -3.10 scripts/daily_all.py   # 完整每日流水线
```

### 书目白名单

> [!IMPORTANT]
> 「每日自动阅读」和「每日听书」**各自只认一本指定的书**，请先把这两本书都加入 QQ 阅读书架。

| 任务 | 目标书 | 书架上找不到时 | 在哪里修改 |
| --- | --- | --- | --- |
| 📖 每日自动阅读 | 书名含「宇智波」：《宇智波：从扉间人柱力开始》 | **严格**：任务以退出码 3 失败，不会改读别的书 | `scripts/auto_read_30min.py` 的 `ALLOWED_BOOK_KEYWORDS`、`TARGET_TITLE_PATTERN`，并同步 `tests/test_autoread_book_guard.py` |
| 🎧 每日听书 | 《全职法师》 | **不严格**：退回打开书架上第一本可见的书 | 本机 `dev/resource/pipeline/qq_reader_trial.json` 中 `AudiobookFindBook` 节点的 `expected` |

- **阅读**：脚本回到书架后用 OCR 找书名，找到才点开；阅读页禁止截图，所以选书这一步就是唯一的校验。失败时日志提示「书架未识别到白名单书目」或「当前书不在自动阅读白名单」。
- **听书**：目前走旧流程（`_backup_old_project_20260909_200716/tools/run_maa_ad.py` + 上述 pipeline），先 OCR 找《全职法师》，找不到时由 `AudiobookOpenFirstShelfBook` 点书架第一本书。因此书架第一本最好就是《全职法师》，否则可能听错书。
- `dev/` 不在 Git 仓库中，听书书目的修改只对本机生效；两处都不能在配置文件或 GUI 里修改。

## 文档

| 文档 | 内容 |
| --- | --- |
| [使用指南](docs/usage.md) | 启动/调试脚本、GUI 界面与按钮、执行语义、快捷键、命令行参数 |
| [配置说明](docs/configuration.md) | `qqreader.local.json` 各字段 |
| [任务与运行机制](docs/tasks.md) | 全部任务及默认参数；ADB 预检、广告、验证码的处理方式 |
| [架构与设计约束](docs/architecture.md) | 目录结构、页面状态机、任务契约、恢复阶梯 |
| [开发、测试与构建](docs/development.md) | pytest、打包 exe、参与开发的规则 |
| [项目规划](docs/PROJECT_PLAN.md) | 需求、验收标准、排障记录 |
| [更新日志](CHANGELOG.md) | 每次改动的原因、修改与验证 |

## 工作原理

```text
GUI / 命令行 ──► 每日流水线（串行、交接前确认书架、验证码即停、记录每步状态）
                   │
                   ▼
             TaskRunner ──► 页面状态机（截图 → 模板 / OCR 多特征识别）
                   │              │
                   │              ├─ 识别不确定 → 恢复阶梯（重截图 → 关弹窗 → 返回 → 重启 App …）
                   │              └─ 检测到验证码 → 求解并复核，失败则等人处理
                   ▼
          MaaFramework（ctypes）──► ADB ──► MuMu 模拟器中的 QQ 阅读
```

每个任务以「契约」声明入口、步骤和成功条件，只有看到成功条件（例如广告卡显示 12/12）才算完成。详见[架构与设计约束](docs/architecture.md)。

## 参与开发

开工前请先阅读 [`AGENTS.md`](AGENTS.md) 和 [`CHANGELOG.md`](CHANGELOG.md) 最上方 3 条。每次改动需在 CHANGELOG 追加记录；Issue 统一记在 Linear（`QQR-xx`）。测试与打包见[开发文档](docs/development.md)。

## 免责声明

本项目仅供个人学习与研究自动化技术，与腾讯 / QQ 阅读官方无关。自动化操作可能违反应用的用户协议，使用风险（包括账号风险）由使用者自行承担。本工具不会执行充值、购买、分享、邀请或第三方授权登录等操作。

## 致谢

- [MaaFramework](https://github.com/MaaXYZ/MaaFramework) —— 图像识别与设备控制框架

旧版 Codex 独立脚本归档在 [`docs/legacy/codex-2026-07-22/`](docs/legacy/codex-2026-07-22/)。
