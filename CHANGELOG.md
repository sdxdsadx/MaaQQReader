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
