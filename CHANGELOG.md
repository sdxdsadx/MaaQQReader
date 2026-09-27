# QQReader 更新日志（CHANGELOG）

每次修改代码、pipeline 覆盖规则、启动脚本或 GUI 行为，都在本文件**最上方**追加一条记录。维护规则见 `AGENTS.md` 的「CHANGELOG」一节。

条目模板：

```markdown
## YYYY-MM-DD · 一句话标题

**触发**：发现问题的来源（哪天哪次运行、哪个任务、日志/记录路径）

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |

**改动文件**：…
**验证**：单元测试结果；实机验证方式（GUI / 命令行）、运行 ID、各任务结果
**未覆盖 / 遗留**：实机没触发到的分支、已知但本次不修的问题
**分支**：任务分支名（例如 `codex/qqr-33-ad-fix-20260927`）
**回滚**：备份位置或 commit
```

---

## 2026-09-27 · 串行任务之间先做交接检查，验证码阻塞不再继续下一项（QQR-53）

**触发**：GUI 批次 `daily_20260927_114947_a58b6564`：等级广告停在「继续观看 / 放弃奖励」挽留弹窗上失败（exit 2），听书随即从广告页启动，`AudiobookBackUntilShelf` 返回 8 次后也失败（`runtime/logs/maafw.log` 第 507 行是听书启动时的画面）。另外离线核对确认：新流程除 SUCCESS 外一律 exit 2，验证码阻塞后继续排下一项是可达的代码路径。

| 模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| 退出码 | 验证码阻塞 / 超时 / 设备错误都是 2 | `scripts/run_task.py` 新流程 `return 0 if result.succeeded else 2` | 新增 `qqreader/runner/exit_codes.py`：10 验证码阻塞、11 超时、12 设备错误、13 取消、20 交接失败；0/2/3 原义不变。新流程用 `exit_code_for_outcome`；设备预检失败、重试耗尽、`MaaClientError` 改为 12 |
| 交接检查 | 前一项结束后不看现场就启动下一项 | GUI `_on_task_finished` 只看退出码并按固定间隔 `_start_next_task` | 新增 `qqreader/runner/handoff.py::check_handoff`：每帧先查验证码（有则不做任何动作，返回 CAPTCHA）；确认书架才 READY；确认框点「取消」、挽留弹窗点「放弃奖励」、书城点书架 tab、开屏点「跳过」，其余返回最多 4 次，再重启一次 App；每个动作后重新截图确认；最后一帧存证据 `screenshots/handoff/`。`run_task.py` 新增 `--task HandoffCheck --next-task --handoff-report` |
| 流水线记录 | 失败原因只剩“子进程退出码 N” | `DailyFlowRun` 只有成功/失败 | `qqreader/workflow.py`：新增步骤状态与流水线状态 `BLOCKED_BY_CAPTCHA`；步骤记录 `outcome`（退出码含义）和 `handoff`（结论、原因、动作、OCR、证据、前项结果）；`apply_handoff` 统一决定启动 / 跳过 / 验证码阻塞；`record_version` 升到 2 |
| GUI 串行 | 同上 | 同上 | `qqreader/gui/app.py`：`_on_task_finished` → `_after_step_finished` → `_start_handoff_check` → `_on_handoff_finished`；退出码 10 或交接发现验证码时停止整轮；交接失败只跳过这一项，下一项再做自己的交接检查。`theme.STEP_STYLES` 增加「验证码阻塞」 |
| `scripts/daily_all.py` | 与 GUI 语义不一致 | 自己写死 0/2 | 改用同一个 `apply_handoff`，每项（第 2 项起）启动前跑 `HandoffCheck`，记录真实退出码 |

**改动文件**：`qqreader/runner/exit_codes.py`（新）、`qqreader/runner/handoff.py`（新）、`qqreader/workflow.py`、`qqreader/gui/app.py`、`qqreader/gui/commands.py`、`qqreader/gui/theme.py`、`scripts/run_task.py`、`scripts/daily_all.py`、`docs/usage.md`、`README.md`、`tests/test_qqr53_handoff.py`（新）、`tests/fixtures/handoff_ocr_frames.json`（新，5 帧真实 OCR，来源写在文件里）、本日志。
**验证**：`tests/test_qqr53_handoff.py` 21 项通过：真实 OCR 帧分类（挽留弹窗、书架、书城+升级弹窗、书架+退出确认框、奖励页上的验证码）；挽留弹窗 → 点「放弃奖励」→ 书架 READY；验证码首帧 / 返回后出现都立即停手（无点击、无返回、无重启）；退不回去 → 返回 + 重启一次 → UNSAFE；GUI 故障注入：等级广告 exit 2 后先跑交接检查，UNSAFE 时听书记为跳过并保留原因，READY 后才启动听书；exit 10 或交接发现验证码时不再启动任何任务。全量 `py -3.10 -m pytest`：375 passed、4 failed、2 skipped，4 项失败与导入基线相同。**未实机验证**：交接检查会按返回键、重启 App，GUI 可能正在使用模拟器，未经用户同意没有在实机上跑。
**未覆盖 / 遗留**：只由单元测试覆盖——实机上的挽留弹窗交接、重启 App 分支、验证码阻塞停整轮。第 1 项任务前不做交接检查（一键执行已先启动 QQ 阅读并清理弹窗；单项运行保留用户选择的起点）。任务间隔等待期间按「停止」仍不会立即生效（原有行为）。旧流程（等级广告、听书）自身识别不到验证码，只能靠下一次交接检查发现。
**分支**：`claude/qqr-53-handoff-20260927`（基于 `claude/import-wip-20260927`）
**回滚**：`git log --oneline -S "串行任务之间先做交接检查" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-09-27 · 入库主检出中已在使用但未提交的工作区改动（QQR-53 前置）

**触发**：用户要求依次修复 QQR-53 / 54 / 55。主检出 `G:\project_X` 的 `master` 工作区有约 2,500 行未提交改动（GUI、广告/奖励/游戏任务、自动阅读、验证码求解器），GUI 每天实际运行的是这版代码，但 Git 里没有；基于 `master` 修复会与之冲突，也会改到过时代码。用户同意先入库再修复。

| 分组 | 文件 | 对应的既有 CHANGELOG 条目 |
| --- | --- | --- |
| GUI | `qqreader/gui/app.py`、`dynamic_plan.py`、`task_catalog.py`，新增 `theme.py`、`widgets.py`；`启动QQReaderGUI.cmd`；测试 `test_dynamic_plan`、`test_gui_task_catalog`、`test_issue12_gui_observability`，新增 `test_gui_stale_settings` | 09-26「修复旧 GUI 沿用 2 分钟任务超时」、09-24「整理启动脚本」 |
| 验证码求解器 | `qqreader/captcha/factory.py`、`slide.py`；`test_qqr29_captcha` | 09-26「滑动验证每 4 次失败刷新」「修正滑块缺口定位」 |
| 自动阅读 | `scripts/auto_read_30min.py`、`_autoread_final300.py`、`_swipe280b.py`；`test_autoread_book_guard` | 09-24「修复 09-23 日志中…阅读失败」 |
| 广告 / 奖励 / 游戏任务 | `qqreader/page/*`、`reward/nav.py`、`runner/recording.py`、`tasks/*`、`scripts/run_task.py` 及对应测试，新增 `test_ad_corner_close` | 09-26「广告观看后识别左右上角 X」「恢复 45 分钟超时」「阅读卡标题 OCR 误读」、09-24 条目 |

**改动文件**：见上表；文件内容与主检出工作区逐字一致（复制，无编辑）。
**未入库**：`qqreader/runner/runner.py`、`tests/test_qqr39_observe_interrupt.py`（QQR-39，另一会话在做）；根目录 `build-gui-exe.cmd`、`start-gui.cmd` 的删除；`runtime/screenshots/ad_watch/captcha_now.png` 的删除（需用户同意）；约 480 个未跟踪的 `scripts/_*.py` 临时脚本和 `docs/` 未跟踪文档；`scripts/live_sendevent.py`（`scripts/live_captcha_auto.py` 依赖它，但内含写死的 `G:\project_X\runtime` 路径，归 QQR-34 处理）。
**验证**：worktree 通过目录联接引用主检出的 `dev/` 与 `_backup_old_project_20260909_200716/` 后，`py -3.10 -m pytest`：353 passed、4 failed、3 skipped。4 项失败都是原本就有的：`test_qqr27_ad_flow::test_ad_play_waits_40_seconds_before_handling_buttons`、`test_ad_round_regressions::test_each_ad_round_has_its_own_initial_wait`（40 秒 vs 35 秒）、`test_ad_round_regressions::test_live_exit_attempt_does_not_restart_eight_swipe_cycle`、`test_issue15_reward_nav::test_live_snap_detects_saved_png_not_raw_screenshot_data`（`live_sendevent` 未入库）。未实机验证（代码与每日实际运行版本相同）。
**未覆盖 / 遗留**：分组提交的中间状态不保证单独可测，只保证最后一个提交全量测试结果如上。
**分支**：`claude/import-wip-20260927`
**回滚**：`git log --oneline -S "入库主检出中已在使用但未提交" -- CHANGELOG.md` 定位后，对 4 个导入提交逐个 `git revert <hash>`。

---

## 2026-09-27 · README 补充每日听书书目说明，合并为「书目白名单」

**触发**：用户要求把每日听书的白名单也写进 README。

| 模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| README.md | 只写了自动阅读白名单，看不出听书固定播放哪本书 | 听书书目只写在本机 `dev/resource/pipeline/qq_reader_trial.json`（`AudiobookFindBook.expected = "全职法师"`） | 「自动阅读白名单」改为「书目白名单」表格，列出两个任务的目标书、找不到时的行为和修改位置；快速开始第 2 步改为两本书都加入书架；功能表「每日听书」注明书名 |

**改动文件**：`README.md`、本日志。
**验证**：未跑测试，原因：仅文档。内容对照 `dev/resource/pipeline/qq_reader_trial.json` 的 `DailyAudiobookFlow` → `AudiobookFindBook` / `AudiobookOpenFirstShelfBook` 节点，以及 `scripts/run_task.py`（`DailyAudiobookFlow` 走 `_run_legacy_task`，无听书相关运行时覆盖）核对。
**未覆盖 / 遗留**：听书不是严格白名单——找不到《全职法师》时 `AudiobookOpenFirstShelfBook` 会打开书架第一本书，可能听错书；这是行为问题，本次只写入文档，未修改。`dev/` 不受 Git 管理，听书书目无法通过仓库同步。
**分支**：`claude/readme-audiobook-whitelist-20260927`
**回滚**：`git log --oneline -S "README 补充每日听书书目说明" -- CHANGELOG.md` 找到提交后 `git revert <hash>`。

---

## 2026-09-27 · README 补充自动阅读白名单说明

**触发**：用户要求在 README 告知自动阅读白名单。README 此前完全没有提到这一限制，新用户书架上没有目标书时，自动阅读会以退出码 3 失败，却看不出原因。

| 模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| README.md | 看不到自动阅读只读指定书目 | 白名单只写在 `scripts/auto_read_30min.py` 的注释和常量里 | 「快速开始」新增第 2 步“把目标书加入书架”；新增「自动阅读白名单」小节：当前关键词「宇智波」、必须在书架上、失败时退出码 3 与日志文案、改书需修改 `ALLOWED_BOOK_KEYWORDS` / `TARGET_TITLE_PATTERN` 并同步测试 |

**改动文件**：`README.md`、本日志。
**验证**：未跑测试，原因：仅文档。说明内容对照 `scripts/auto_read_30min.py`（`ALLOWED_BOOK_KEYWORDS`、`BookNotAllowed` → `return 3`）和 `scripts/run_task.py::_run_reading_task`（`DailyReadingFlow` 调用该脚本）核对。
**未覆盖 / 遗留**：白名单仍是源码常量，不能从配置或 GUI 修改；`scripts/auto_read_30min.py` 工作区有未提交改动，本次未触碰。
**分支**：`claude/readme-autoread-whitelist-20260927`
**回滚**：`git log --oneline -S "README 补充自动阅读白名单说明" -- CHANGELOG.md` 找到提交后 `git revert <hash>`。

---

## 2026-09-27 · README 重构为项目首页，详细说明拆到 docs/

**触发**：用户反馈 README 不是简介页（310 行，全是操作手册），要求参考优秀开源项目重构。

| 模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| README.md | 打开后看不到项目是什么、能做什么、现在到什么程度，直接进入脚本菜单和 GUI 布局细节 | 使用手册、配置、架构、测试都堆在 README | 重写为约 110 行的首页：一句话介绍与徽章 → 功能表 → 项目状态（已验收/未验收）→ 3 步快速开始 → 文档导航 → 工作原理图 → 参与开发 → 免责声明 → 致谢 |
| docs/ | — | — | 新增 `usage.md`（启动/调试脚本、GUI、命令行）、`configuration.md`、`tasks.md`（任务一览 + 运行机制）、`architecture.md`（项目结构 + 设计约束）、`development.md`（测试与构建 + 参与开发）；内容由旧 README 对应章节原样迁移，仅修正相对链接 |

**改动文件**：`README.md`、`docs/usage.md`、`docs/configuration.md`、`docs/tasks.md`、`docs/architecture.md`、`docs/development.md`（均新增）、本日志。
**验证**：未跑测试，原因：仅文档。检查了旧 README 除「目录」「已知限制」外的全部章节都已迁入 docs/，「已知限制」并入 README 的「项目状态」。
**未覆盖 / 遗留**：仓库没有 LICENSE，README 未写许可证；没有 GUI 截图，首页暂无配图。
**分支**：`claude/readme-restructure-20260927`（工作区其余未提交改动不属于本任务，未一并提交）
**回滚**：`git log --oneline -S "README 重构为项目首页" -- CHANGELOG.md` 找到提交后 `git revert <hash>`。

---

## 2026-09-27 · 补全 .gitignore，把 GUI 下的 Git 操作流程写入 AGENTS.md

**触发**：同日把 `claude/agents-git-rules-20260927` 推到 GitHub 时遇到的问题。GitHub Desktop 未添加本仓库；授权页被全局 `.gitconfig` 的 `url.insteadOf` 转到第三方代理 `ghfast.top`，报 “Invalid input”；GitHub Desktop 因为远端叫 `github`，一度提示“Publish repository”（新建仓库）；工作区有 559 个未提交文件，其中大部分是本应忽略的 `.hermes/` 等目录。用户要求把流程写进 AGENTS.md，方便其他 agent 使用。

| 模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| `.gitignore` | `runtime/`、`configs/*.local.json`、`.hermes/`、`.serena/`、`_backup_*/`、`*.bak*`、`*.exe` 未被忽略 | 旧文件只忽略缓存和打包产物 | 补齐上述规则；`*.spec` 保留忽略，已确认 `scripts\build-gui-exe.cmd` 用命令行参数调用 PyInstaller，不读取 `QQReaderGUI.spec` |
| AGENTS.md | 只能操作 GUI 的 agent 不知道怎么建分支、只提交部分文件、推送和核对远端 | 此前只写了 git 命令 | 新增「本机操作方式」小节：GitHub Desktop 步骤、远端核对 API、ghfast 授权页警示、pytest 限制；写明远端 `master` 是主线、`main` 是旧分支 |
| 全局 git 配置 | GitHub 请求走 `ghfast.top` | 用户全局 `.gitconfig` 中的 `url "https://ghfast.top/https://github.com/"` 与对应 `credential` 段 | 由用户本人删除（非本仓库文件，未提交）；删除后直连 github.com 推送成功 |

**改动文件**：`.gitignore`、`AGENTS.md`、本日志。
**验证**：远端分支经 `https://api.github.com/repos/sdxdsadx/MaaQQReader/branches` 核对；远端 `master` 文件清单经 git/trees API 核对，只有 `runtime/screenshots/ad_watch/captcha_now.png` 属于应忽略内容。仅改文档和忽略规则，未跑 pytest。
**合并前 pytest**：用户 2026-09-27 14:00 运行（测试对象是工作区代码，含未提交改动），4 项失败：`test_qqr27_ad_flow::test_ad_play_waits_40_seconds_before_handling_buttons`、`test_ad_round_regressions::test_each_ad_round_has_its_own_initial_wait`（这两项是 40 秒与代码 35 秒不一致，见 2026-09-24 条目）、`test_issue15_reward_nav::test_detect_slide_accepts_real_captcha_fixture`（`captcha_now.png` 已被删除）、`test_ad_round_regressions::test_live_exit_attempt_does_not_restart_eight_swipe_cycle`（直播退出期望 PRESS_BACK、实际 WAIT，未单独确认是否为旧问题）。用户确认带着这 4 项已知失败合并到 `master`；合并前的 `master` 为 `4333246`，本地保护分支 `backup/20260927-before-merge`。
**未覆盖 / 遗留**：`captcha_now.png` 仍被跟踪（停止跟踪需用户同意）；远端没有 `dev/`（Maa 资源目录）和 `_backup_old_project_20260909_200716/`，从 GitHub 克隆的仓库不能直接运行；工作区其余未提交改动未处理。
**分支**：`claude/agents-git-rules-20260927`
**回滚**：`git log --oneline -S "补全 .gitignore，把 GUI 下的 Git 操作流程" -- CHANGELOG.md` 找到提交后 `git revert <hash>`。

---

## 2026-09-27 · 按 AGENTS.md 规范精简入口文档并补齐 Git / GitHub 规范

**触发**：用户要求按项目实际运行方式重写 AGENTS.md，重点是 Git 备份与 GitHub 上传规范，并参照 agents.md 官方格式和 Codex 文档。旧 AGENTS.md 约 30 KB，接近 Codex 默认读取上限 32 KiB（`project_doc_max_bytes`），而且仓库现状描述已经过期（写着“无远端”“G 盘只读”）。

| 模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| AGENTS.md | 需求、架构、审计和操作规则混在一起；Git 规则只有一句“按授权保存 Git 提交” | 入口文档承担了项目规划书的职责 | 按 agents.md 常见结构重写为约 8 KB 的操作手册：Project overview / Dev environment / Testing / Domain rules / CHANGELOG / Git & GitHub / Security & data / Done checklist |
| docs/PROJECT_PLAN.md | — | — | 新增：原 AGENTS.md 中的问卷结论、架构、验收场景、失败记录、待确认项全部迁入；附待处理的 Git 问题和推荐的 `.gitignore` / `.gitattributes` |
| 本次试跑发现 | 直接双击 `dist\QQReaderGUI.exe` 时提示“请先加载本机配置文件”；听书任务调用 `_backup_old_project_20260909_200716\tools\run_maa_ad.py` | 配置和端口由 `启动QQReaderGUI.cmd` 写入；听书尚未迁入新工程 | 写入 AGENTS.md：GUI 必须用启动脚本打开；旧工程备份目录是运行依赖，不能移动 |

**改动文件**：`AGENTS.md`、`docs/PROJECT_PLAN.md`（新增）、本日志。
**验证**：GUI（`启动QQReaderGUI.cmd` 启动）「选择1分钟试跑」→「直接运行已选」，run `daily_20260927_182428_e0624ca6`：每日自动阅读 成功 02:00、每日游戏 成功 03:10、每日听书 成功 01:45，记录 `runtime/records/daily_flows/daily_20260927_182428_e0624ca6.json`。本次只改文档，未跑 pytest。
**未覆盖 / 遗留**：`docs/PROJECT_PLAN.md` §7 列出的 Git 问题（codex 分支上游指向 master、`.gitignore` 缺项、无 `.gitattributes` 等）本次未处理；听书日志中有一条 MaaNS `adb shell settings get secure android_id` 的 ERR，但任务成功，未排查。
**分支**：`claude/agents-git-rules-20260927`
**回滚**：`git log --oneline -S "按 AGENTS.md 规范精简入口文档" -- CHANGELOG.md` 找到提交后 `git revert <hash>`。

---

## 2026-09-27 · 将 Codex 旧版 QQ 阅读脚本归档到 G 盘

**触发**：用户要求合并 Codex 文件夹中的 QQ 阅读自动化脚本与 `G:\project_X`，以后只在 G 盘记录和维护。

| 模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| QQ 阅读脚本位置 | `Documents\Codex` 还保留一套独立的 2026-07-22 脚本和启动入口 | 早期脚本在 Codex 输出目录，未归入现行 MaaFramework 工程 | 原样归档源码、任务模块、图片和说明到 `docs/legacy/codex-2026-07-22/`；历史日志及截图放 `runtime/legacy/`；三个启动文件和两个 Python 入口转向 G 盘 GUI；文档声明 G 盘为唯一维护目录 |

**改动文件**：`docs/legacy/codex-2026-07-22/`、`AGENTS.md`、`README.md`、本日志；Codex 旧目录的三个启动文件和两个 Python 入口；D 盘旧项目的 `AGENTS.md` 迁移提示。
**验证**：迁移的 24 个原始文件逐一比对 SHA-256 一致；核对旧版阅读、听书、游戏、面板功能在 G 盘已有对应实现。未运行模拟器或 GUI。
**未覆盖 / 遗留**：旧版模板未在当前设备重新标定，未加入现行识别链路；历史日志和截图仅在本机保留。
**回滚**：G 盘三个文档的修改前副本在 `runtime/migration-backups/2026-09-27-codex-script/`；Codex 原始脚本保留，旧启动入口原文见归档。

---

## 2026-09-26 · 修复旧 GUI 沿用 2 分钟任务超时

**触发**：`runtime/logs/gui_DailyAdFlow_20260926_143304.log` 仍传 `--timeout-minutes 2`，验证码首轮成功后广告任务在播放中 `TIMEOUT`；磁盘 `runtime/gui_tasks.json` 已设置广告 45 分钟，GUI 进程从前一日持续运行。

| 模块 | 根因 | 修改 |
| --- | --- | --- |
| GUI 任务启动 | 任务设置只在打开 GUI 时读取，外部更新后内存仍留旧值 | 每次开始串行或单项任务前重新读取磁盘设置 |
| 正式每日预设 | 只恢复阅读/游戏时长，不恢复 `timeout_minutes` | 正式预设一并恢复各任务默认超时，广告为 45 分钟 |

**改动文件**：`qqreader/gui/app.py`、`qqreader/gui/task_catalog.py`、`tests/test_gui_task_catalog.py`、`tests/test_gui_stale_settings.py`。
**验证**：GUI 设置与命令相关 21 项定向测试通过；测试覆盖内存 2 分钟、磁盘 45 分钟时新任务命令传 45 分钟。15:29 已关闭旧 GUI 并重新启动，新窗口正常响应；真实广告任务尚未重新运行。
**未覆盖 / 遗留**：完整广告流程是否在 45 分钟内结束仍需实机验收。
**回滚**：撤销本次 GUI 设置加载和正式预设改动。

---

## 2026-09-26 · 滑动验证每 4 次失败刷新，总计最多 16 轮

**触发**：用户要求连续 4 次失败后点击滑块框左下角刷新继续尝试；`runtime/logs/gui_DailyAdFlow_20260926_143304.log` 和 `runtime/records/DailyAdFlow_20260926_143525_874148.json` 用于排查这次“只执行一次就失败”。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| 滑动验证码求解 | 轨道/缺口首轮重拍仍识别不到时，原求解器立即退出；连续滑动不通过时没有主动刷新拼图 | `solve()` 的二次检测失败分支直接 `return solved=False`，刷新按钮不在求解循环中 | 检测失败也计入失败轮次；每连续 4 轮失败且 OCR 确认验证码仍在时，点击已截图确认的左下角刷新 `(125,897)`，之后用新帧重检测；最多 16 轮且至多 16 次滑动，耗尽后等待人工 |
| 本次 DailyAdFlow 结果 | 用户观察为“一次就失败” | 这次实际第 1 次滑动成功并确认验证码消失，任务在第 3 条广告播放时因 GUI 仍传入 `--timeout-minutes 2` 而 `TIMEOUT`；保存的 `runtime/gui_tasks.json` 已是 45 分钟，但旧 GUI 进程持有 2 分钟内存值 | 验证码求解逻辑按上述临时方案更新；下次完整任务需重新打开 GUI 使 45 分钟设置生效 |

**改动文件**：`qqreader/captcha/slide.py`、`qqreader/captcha/factory.py`、`tests/test_qqr29_captcha.py`、本日志；新仓库同步修改对应求解器、测试和说明。
**验证**：针对性单元测试验证第 4、8、12 次失败后刷新 3 次、第 16 次不再刷新、检测失败后可进入下一轮；本次实际运行仅验证第 1 次滑动通过，并没有触发 4 次失败刷新分支。
**未覆盖 / 遗留**：实机连续 4 次失败后刷新尚未出现；验证码状态无法确认时停止自动点击。旧 GUI 进程在重启前仍会传入 2 分钟超时。
**回滚**：撤销本条求解器轮数、刷新逻辑与对应测试，保留先前缺口定位修复。

---

## 2026-09-26 · 广告观看后识别左右上角 X 并确认退出

**触发**：用户指出观看约 40 秒后无法识别并点击顶部关闭按钮；`runtime/screenshots/20260926/DailyAdFlow_20260926_114151_685663_008_TIMEOUT.png` 显示左上角 X 在约 `(48,70)`，当时仍停在广告页。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| DailyAdFlow 广告关闭 | 倒计时结束后仍停留广告页，部分分支点 `(53,112)` 或依赖 OCR “X” 后退回返回键 | 固定坐标低于实际 X；OCR 漏读时没有图像定位，右上角还有形似圆形关闭键的静音按钮 | 在最新截图的左右上角优先定位 X 的 OCR 框或圆圈双对角线；排除只有单斜线的静音钮；普通广告在等待结束后立即尝试，直播广告仍在规定滑动后才退出；点击后仍由页面状态确认返回 |

**改动文件**：`qqreader/tasks/ad.py`、`tests/test_ad_corner_close.py`、`tests/test_issue2_offerwall.py`、`tests/test_qqr31_live_ad.py`、本日志。
**验证**：15 个针对性测试通过；3 张留存广告截图均离线定位到约 `(48,71)`，奖励页截图不命中。实机单广告验证保存在 `runtime/screenshots/ad_close_real_20260926_130416/`：点击“立即观看”，40 秒后截图显示“恭喜获得奖励”和顶部 X，代码定位 `(48,71)` 并点击，下一帧已回到奖励页，视频计数显示 `4/12`，同时出现滑动验证码。
**未覆盖 / 遗留**：验证码出现后按阻塞规则停止自动点击；未继续完成 12/12。右上角关闭 X 由合成图像与 OCR 框测试覆盖，未在本次实机广告出现。GUI 控制工具初始化失败，本次实机为 Maa 客户端单广告验证，未运行完整 GUI 日常流程。
**回滚**：撤销上述广告关闭定位逻辑与对应测试；留存实机截图用于对照。

---

## 2026-09-26 · 恢复完整广告流程的 45 分钟超时

**触发**：`runtime/logs/gui_DailyAdFlow_20260926_104253.log` 和 `runtime/logs/gui_DailyAdFlow_20260926_113934.log` 均以 `独立超时 120s` 结束；对应运行记录分别为 `runtime/records/DailyAdFlow_20260926_104530_673468.json`、`runtime/records/DailyAdFlow_20260926_114151_686171.json`。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| DailyAdFlow 本机 GUI 设置 | 第一轮通过滑块验证并进入下一条广告、第二轮进入第 3 条广告后均超时 | `runtime/gui_tasks.json` 将完整 12 条广告任务的 `timeout_minutes` 保存为 `2.0`，短于任务所需时间；任务目录默认值为 45 分钟 | 先备份，再只将该项恢复为 `45.0` |

**改动文件**：`runtime/gui_tasks.json`（本机运行配置，Git 忽略）、本日志。
**验证**：对照备份确认仅一个超时值变化；读取 GUI 任务配置确认为 45 分钟。两次故障运行的实机记录表明广告仍在推进，第一轮滑块验证成功；修改后的完整 GUI 流程尚未运行。
**未覆盖 / 遗留**：已打开的 GUI 仍持有原设置，须重新打开 GUI 后再运行；45 分钟内完成 12 条广告的业务结果未验证。
**回滚**：用 `runtime/gui_tasks.json.bak-20260926_114525-ad-timeout` 恢复原文件。

---

## 2026-09-26 · 阅读卡标题 OCR 误读为“赠市”时仍可领奖

**触发**：`runtime/logs/gui_DailyReadingFlow_20260925_203458.log` 于 21:13:39 报“奖励页未找到‘每日阅读领赠币’卡片”；同次 Maa 日志 21:13:21~37 连续识别为“每日阅读领赠市”，同时识别到两枚“领取”按钮。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| DailyReadingFlow 领奖 | 卡片实际存在却报未找到 | `reading_card_bounds` 只匹配末字“币”，未覆盖实测 OCR 的“市” | 仅接受“每日阅读领赠[币市]”，按钮仍限定在阅读卡范围内 |

**改动文件**：`qqreader/tasks/reading_reward.py`、`tests/test_reading_reward_claim.py`、本日志。
**验证**：Luna 独立执行 `py -3.10 -m pytest tests/test_reading_reward_claim.py -q`，6 项通过；其中一项走完整假客户端领奖路径，标题始终误读为“赠市”仍完成等待刷新、点击与到账判断。没有修复后的实机 GUI 运行 ID。
**未覆盖 / 遗留**：真实设备下一次出现相同 OCR 误读时的 GUI 结果未验证；2026-09-25 21:13 后的一轮正常阅读已成功，故本次未重复运行 35 分钟任务。
**回滚**：仅撤销阅读卡标题匹配与对应两条测试；不触碰仓库其他已有修改。

---

## 2026-09-26 · 修正滑块缺口定位并将滑动上限设为 15 轮

**触发**：2026-09-25 `DailyAdFlow_20260925_221915_620426`；`runtime/logs/gui_DailyAdFlow_20260925_221713.log` 与同名运行记录显示验证码出现后滑动 6 轮仍在，结果为 `BLOCKED_BY_CAPTCHA`；对应截图在 `runtime/screenshots/20260925/`。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| 滑动验证码 | 6 轮后仍显示验证码 | 留存截图的 Canny 最强列落在缺口左边缘附近 `x=492`，原算法直接当目标；实际应取缺口边缘中点 | `qqreader/captcha/slide.py` 在可信宽度内汇总右侧强边缘，留存截图目标改为约 `x=532`；单次最多 15 轮 |
| 验证码守卫 | 整轮求解可能再次启动 | 默认 guard 允许 2 次完整求解，使实际滑动总数可能超过上限 | `qqreader/captcha/factory.py` 默认只执行 1 次完整滑动求解，未通过继续等待人工 |

**改动文件**：`qqreader/captcha/slide.py`、`qqreader/captcha/factory.py`、`tests/test_qqr29_captcha.py`、本日志。
**验证**：`py -3.10 -m pytest tests/test_qqr29_captcha.py -q` 为 13 通过、1 跳过；留存截图离线检测目标约 `x=532`。未启动实机 GUI 流程，尚无修复后的运行 ID 或任务结果。
**未覆盖 / 遗留**：实际滑动是否被 QQ 阅读接受仍须在下一次验证码出现时经 GUI 单任务运行确认；15 轮可能超过 2026-09-25 那次临时设置的 2 分钟任务超时，验证时需给广告任务足够时间。
**回滚**：仅撤销上述三个代码/测试文件中本条对应的改动；不触碰仓库其他已有修改。

---

## 2026-09-24 · 整理启动脚本：根目录只保留「启动」和「调试」两个

**触发**：用户要求仓库根目录的 bat/cmd 只保留两个，一个日常启动，一个调试。

| 项目 | 之前 | 现在 |
| --- | --- | --- |
| 日常启动 | `启动QQReaderGUI.cmd`，外加内容完全相同的 `start-gui.cmd` | 只保留 `启动QQReaderGUI.cmd`（沿用原名，桌面快捷方式不失效） |
| 调试 / 冷启动 | `冷启动QQReader.cmd`（gui/run/stop/status） | 新文件 `调试QQReader.cmd`：双击出菜单（体检、冷启动+GUI、`/cold` 重启模拟器、识别检查、单任务运行、单元测试、冷停止）；命令行参数新增 `smoke` / `task` / `test` |
| 打包 | 根目录 `build-gui-exe.cmd` | 移到 `scripts\build-gui-exe.cmd`，ROOT 改为上一级目录 |
| 其他 | 5 个 `.bak-*` 备份、`start-gui.cmd`、`启动QQReaderGUI.cmd - 快捷方式.lnk`、2 个 `验证修复_*.cmd` | 全部移到 `runtime/_claude_backup_20260924/launchers/`，没有删除 |

**踩坑（已处理）**：
- UTF-8 + `chcp 65001` 的中文批处理，在 cmd 里会随机把部分行错位解析，出现“xxx 不是内部或外部命令”（09-24 实测：新增的注释行和帮助行被当成命令执行）。
- `MuMuManager` / Python / PowerShell 执行后，会把控制台代码页改成 65001，之后读到的 GBK 行会变成乱码。
- 处理：`调试QQReader.cmd` 以 **GBK** 保存并使用 `chcp 936`；每次调用外部程序后重新执行 `chcp 936`；需要判断退出码的地方先保存 errorlevel 再切代码页；PowerShell 调用里不再设置 `[Console]::OutputEncoding`。
- **以后编辑这个文件必须保持 GBK 编码。**

**改动文件**：新增 `调试QQReader.cmd`、`scripts/build-gui-exe.cmd`；修改 `启动QQReaderGUI.cmd`（只加了一行注释）、`README.md`（快速开始、调试脚本、构建说明）、`scripts/package_release.py`（打包清单）、`tests/test_run_task_post_rewards.py`。
- 最后这个测试之前没有替阅读子进程打桩，跑测试时会真的去连模拟器；现在已打桩，测试通过。

**验证**：
- 在 Windows 上实际运行 `调试QQReader.cmd status` 和 `test`：已没有“不是内部命令”的报错，也没有乱码。
- `status` 正确输出模拟器、adb、配置端口；`test` 能正常调起 pytest。

**未覆盖 / 遗留**：
- 双击菜单需要键盘选择，没有实机点选验证。
- `smoke`、`task`、`gui` 模式需要模拟器在线，本次没跑。
- `启动QQReaderGUI.cmd` 仍是 UTF-8 + `chcp 65001`，内容没改；用户日常使用正常，如果以后也出现“不是内部命令”的报错，按同样方法改成 GBK。

**回滚**：旧脚本都在 `runtime/_claude_backup_20260924/launchers/`，移回根目录即可。

## 2026-09-24 · 修复 09-23 日志中游戏 / 广告 / 等级广告 / 阅读失败

**触发**：2026-09-23 18:36 那轮完整流水线（`runtime/records/daily_flows/daily_20260924_003633_6de90032.json`），以及当天更早的几次运行。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| DailyGameFlow | 挂机 35 分钟后 TIMEOUT，“开始挂机计时”和“暂不计时”交替出现 190 多次 | `_RUNNING_BLOCK_TEXTS` 里有“活动/同意/新游”这类泛词，游戏 HUD 的「活动」按钮和聊天滚动文字会间歇命中，每次都把 `game_started_at` 清零 | 计时开始后只认强加载信号（`_RUNNING_STRONG_LOADING_TEXTS`），并且永不清零已累计的时间（`qqreader/tasks/game.py`） |
| DailyGameFlow | 从「我的」tab 开始时一直“未定位到特征 home_ocr_reward_entry”，空等到超时 | HOME 状态下没有奖励入口时不会切 tab | HOME 且没有奖励入口时，先点「书架」tab，最多 3 次（`game.py`） |
| DailyAdFlow | `ad_exit_unconfirmed`：已显示“恭喜获得奖励”，仍停在广告页 | 「了解详情」类广告不响应返回键；退出守卫只尝试一次、20 秒后直接判致命失败 | 出现“恭喜获得奖励”时直接点左上角 X；退出 20 秒没生效时，依次改点 X、再按一次返回，仍无效才判失败（`qqreader/tasks/ad.py`） |
| DailyLevelAdFlow | 点「等级」后 20 秒没进入等级页（20:30） | 点击被青少年模式提示吞掉，`LevelClickLevelIcon` 的 next 只有 `LevelPageReady`，不会重试 | 新增 `LevelTeenModeDismiss`、`LevelClickLevelIconAgain`（最多 3 次）。**不能按 OCR 识别到的 “X” 关弹窗**：「我的」页「基因」图标会被读成 X（`scripts/run_task.py` 的 `_apply_level_entry_popup_overrides`） |
| DailyLevelAdFlow | 积分行没有“今日已完成”，校验失败（18:16） | 点「看小视频」后广告没拉起来，链路把等级页当广告去下滑 | 新增 `LevelPointsAdNotStarted` / `LevelCoinAdNotStarted`（等待）和 `...AdAgain`（重新点击）（`_apply_level_ad_launch_retry_overrides`） |
| DailyLevelAdFlow | 积分广告是浏览型，被“跳过”放弃，积分没到账（09-24 验证时发现） | 返回等级页后没有重试 | `LevelAfterPointsAd` / `LevelVerifyPointsScroll` 的 next 加入 `LevelClickPointsAdAgain`，换一条广告重试，最多 2 次 |
| DailyReadingFlow | 35 分钟阅读正常完成，但领奖失败（exit 2） | 阅读刚结束时服务器还没同步阅读时长，领奖逻辑只看一次；证据截图用固定文件名，被下一次覆盖 | 没有可领按钮时，等 20 秒后刷新奖励页再看，最多 3 次；证据另存带时间戳的副本；失败原因里附上阅读卡片的文字（`qqreader/tasks/reading_reward.py`） |
| 运行记录 | 记录和截图文件名是 `19700102_…` | `FileRunRecorder` 用单调时钟（开机秒数）生成文件名 | 文件名改用墙钟时间（`qqreader/runner/recording.py`） |
| 可观测性 | `gui_*.log` 只有 “task start” 一行，看不到结果 | 结果只打印到 stdout | 写入 `task end exit=…`、`outcome/reason/record`、阅读奖励结果（`scripts/run_task.py`） |

**改动文件**：`qqreader/tasks/game.py`、`qqreader/tasks/ad.py`、`qqreader/tasks/reading_reward.py`、`qqreader/runner/recording.py`、`scripts/run_task.py`；测试 `tests/test_game_adapter_timer.py`、`tests/test_issue2_offerwall.py`、`tests/test_level_ad_runtime_overrides.py`、`tests/test_reading_reward_claim.py`。

**验证**：
- 单元测试：新增 9 个测试全部通过；Windows 上相关的 29 个测试通过。另有 14 个测试原本就失败，本次没动（见下方遗留）。
- 实机（命令行，`runtime/logs/verify_20260924.log`）：DailyGameFlow SUCCESS，挂机计时只启动 1 次。
- 实机（GUI「直接运行已选」，run `daily_20260924_101436_7366b9d7`）：DailyAdFlow SUCCESS（12/12），DailyReadingFlow SUCCESS。
- 实机（GUI「单独运行此任务」，run `daily_20260924_111017_84048d25`）：DailyLevelAdFlow SUCCESS。上一次重跑失败是 adb `input swipe` 返回 255，属于环境偶发。

**未覆盖 / 遗留**：
- 广告退出后改点 X 的兜底、阅读奖励等同步后重试、积分广告放弃后重试：这三条实机都没触发到，只由单元测试覆盖。
- 原本就失败的 14 个测试，本次没修：
  - `test_run_task_post_rewards`、`test_issue13_legacy_timeout`：测试和代码不同步（阅读已改走 `auto_read_30min.py`）。
  - `test_qqr27` / `test_ad_round_regressions`：测试期望 40 秒，代码里 `initial_wait_seconds=35`，与 README 不一致。
  - `test_issue15` 用到的 `captcha_now.png` 已被删除。
- 09-23 11:25 那次游戏任务 `OSError: [Errno 22]`：怀疑是 GUI 关闭后 stdout 管道失效，证据不足，没有处理。

**回滚**：改动前的文件在 `runtime/_claude_backup_20260924/before_fix.tgz`；本次改动还没有提交到 git。
