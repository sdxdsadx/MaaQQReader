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

## 2026-10-28 · 可移植适配：多模拟器自动发现、分辨率兼容检查，修复非 720 宽设备上阅读点错书

**触发**：用户要求做可移植适配，重点验证不同分辨率、不同模拟器的通用性，并上传 GitHub、发布新 release。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| 启动器 `启动QQReaderGUI.cmd` | 写死 `D:\Program Files\Netease\MuMu Player 12\shell`、实例 0、默认端口 16384；别的盘符或别的模拟器找不到设备 | 第 2–5 步只认 MuMuManager | 新增 `qqreader/maa/emulator.py`：从配置、注册表和各盘符的默认安装目录找 MuMu 12（`shell\` / 4.x `nx_main\`）、雷电 9、BlueStacks 5、夜神、逍遥及 PATH 里的 adb；按「配置地址在线 → 管理工具（`MuMuManager info -v all` / `ldconsole list2` / `bluestacks.conf`）→ `adb devices` → 默认端口」找设备；没有偏好时按 MuMu → 雷电 → BlueStacks → 夜神 → 逍遥的顺序选；MuMu / 雷电 / 逍遥可自动拉起；只回写 `adb_path` / `adb_address` / `emulator_path`（路径只差斜杠时不改写）；没有本机配置时按示例生成。默认端口先做 0.3 秒 TCP 探测（无设备时探测从 43 秒降到 7 秒）。启动器第 2–5 步改为调用 `prepare --launch`，实例序号可用 `QQREADER_EMULATOR_INDEX` 指定 |
| `调试QQReader.cmd` | 同样写死 MuMu 目录 | 同上 | MuMu 目录优先取本机配置 `emulator_path`（MuMuManager.exe 所在目录），实例序号读 `QQREADER_EMULATOR_INDEX`；保持 GBK |
| 分辨率（新增 `qqreader/maa/display.py`） | 横屏、非 9:16、DPI 不匹配的设备上任务跑到一半才识别失败，看不出原因 | 坐标按 720×1280 / 240 DPI 标定（实测日常 MuMu：`wm size` 720x1280、`wm density` 240），之前没有任何检查 | 读 `wm size` / `wm density`（Override 优先）判定：一致 ok；9:16 且 DPI 等比 warn（提示滑块 sendevent 用设备像素）；横屏 / 非 9:16 / 逻辑宽度偏差 >5% fail。`CtypesMaaClient._create_controller` 连接 ADB 设备时调用 `enforce_display`：fail 拒绝连接并给出改法，`QQREADER_DISPLAY_CHECK=warn/off` 可降级。体检 `doctor` 新增「截图坐标系」「设备分辨率」两项 |
| 自动阅读 `scripts/auto_read_30min.py` | 1080×1920 / 360 DPI 实机：点书名后进了「我的笔记」，exit 3 | 书名 OCR 框是 Maa 的 720 坐标，脚本却用 `adb shell input tap` 直接点设备像素（720 坐标 (294,462) 落在上一行「我的笔记」） | 新增 `to_device` / `swipe`：启动时读设备分辨率，`tap` 与正文上滑都按 `设备短边/720` 换算 |
| 听书封面截取 `qqreader/gui/cover.py` | 1080 宽设备上截出的封面比 Maa 截图里的大 1.5 倍，模板匹配不到 | `capture_screen_png` 返回原始像素截图 | 新增 `normalize_short_side`，截图先缩放到短边 720 |
| 离线自定义控制器 `CtypesMaaClient` | 离线喂图做 OCR 报 `Tasker not inited` | 自定义控制器创建后没有 `PostConnection`，也没设短边 | 补设短边与连接 |
| MFA `interface.json` | 控制器名「MuMu安卓端」 | — | 改为「安卓模拟器（ADB）」，由 `qqreader/mfa/interface.py` 重新生成 |

**改动文件**：`qqreader/maa/emulator.py`（新增）、`qqreader/maa/display.py`（新增）、`qqreader/maa/ctypes_client.py`、`qqreader/maa/doctor.py`、`qqreader/gui/cover.py`、`qqreader/mfa/interface.py`、`mfa/interface.json`、`scripts/auto_read_30min.py`、`启动QQReaderGUI.cmd`、`调试QQReader.cmd`、`tests/test_emulator_detect.py`（新增）、`tests/test_display_compat.py`（新增）、`tests/test_resolution_scaling.py`（新增）、`tests/fixtures/images/reward_home_720x1280_20261019.png`（新增，10-19 实机奖励页截图，无账号信息）、`tests/test_maa_adapter.py`、`tests/test_mfa_interface.py`、`docs/portability.md`（新增）、`README.md`、本日志。
**验证**：
- 单元测试：新增 3 个文件。`test_resolution_scaling.py` 用真实截图放大到 1080×1920、1440×2560 后交给真实 MaaFramework（自定义控制器、短边 720）：三种分辨率截图都缩放回 720×1280，OCR 读到同样的 4 处关键文字、中心偏差 ≤6px，点击 (360,640) 分别映射到 (540,960)、(720,1280)；没有 Maa 运行时自动跳过。`test_display_compat.py` 含阅读脚本换算回归（复现 1080 实机误点的坐标）。`test_maa_adapter.py` 的体检检查项清单加上「截图坐标系」。
- 全量 `py -3.10 -m pytest`（worktree，`dev/` 与 `_backup_old_project_20260909_200716` 以目录联接接入）：773 passed、3 failed、2 skipped（18.0s）。3 项失败是已知的 40 / 35 秒不一致（`test_ad_round_regressions` ×2、`test_qqr27_ad_flow` ×1），与 10-19 条目的基线相同。
- 实机（命令行 `scripts/run_task.py`，worktree 代码，MuMu 12 实例 0）：
  - 720×1280 / 240：体检通过；`LaunchQQReader` exit 0；`DailyReadingFlow --minutes 1` 07:14–07:16 exit 0（正文停留 1 分钟，阅读奖励已领）。
  - `wm size 1080x1920` + `wm density 360`：体检通过（warn）；`DailyReadingFlow` 修复前 07:16–07:17 exit 3（误入「我的笔记」），修复后 07:19–07:20 exit 0（日志「按 ×1.5 换算」，正文停留 1 分钟）。
  - `DailyGameFlow --duration-minutes 1`：1080×1920 07:21–07:36 TIMEOUT，720×1280 基线 07:37–07:52 同样 TIMEOUT，两次都是滚到奖励页底仍找不到「玩游戏 / 在线时长」任务行（今天页面上没有这一行），与分辨率无关。
  - `wm density 320`：体检与 `LaunchQQReader` 都在连接时被拒绝（exit 12），提示改 DPI 240。
  - 测试后 `wm size reset`、`wm density reset`，已确认恢复 720x1280 / 240。
  - 启动器：用截断副本（在启动 GUI 前退出、`ROOT` 指向本 worktree）实跑第 1–5 步。首次实跑暴露两处问题：① 新写的一行中文 `rem` 注释在 936 / 65001 代码页下都被 cmd 拆成命令执行（报「不是内部或外部命令」），改成英文后两种代码页都干净；② 全新配置时注册表里只有雷电（本机 MuMu 12 没有卸载注册项），拉起了雷电实例 0（横屏 1920×1080，分辨率检查正确判 fail）。已加默认安装目录扫描和 MuMu 优先，复查 `discover_installations` 依次返回 MuMu、雷电、platform-tools。被拉起的雷电实例已关闭。
  - `调试QQReader.cmd`（GBK）：截取变量段实跑。没有配置时 `MUMU_DIR` 为默认目录；配置 `emulator_path` 为 `X:\Nowhere 测试\MuMu\shell\MuMuManager.exe` 时取到 `X:\Nowhere 测试\MuMu\shell`；`QQREADER_EMULATOR_INDEX=2` 时 `VMINDEX=2`。`status` 模式输出正常。
  - 雷电 9 实例 2（720×1280 / 320，新建实例默认值）：`prepare --launch` 28 秒拉起并选中 127.0.0.1:5559；体检严格模式拒绝，`QQREADER_DISPLAY_CHECK=warn` 下连接、截图、OCR（21 条）、点击通过；临时 `wm density 240` 后判定 ok，随后复原并关闭实例。没有本机配置、没有路径提示时，从注册表找到雷电并按示例生成配置。实例名起初显示乱码（`PYTHONUTF8=1` 下按 UTF-8 解 GBK），改为按 `GetACP()` 解码后正常，补了回归测试。
**未覆盖 / 遗留**：
- 滑块验证码 `qqreader/captcha/slide.py` 的 sendevent 拖动直接写 720 坐标系的数值，非 720 宽设备上大概率拖错位置；该模块按 AGENTS.md 禁止修改，只在分辨率检查的 warn 提示里写明。需要用户同意后另开任务。
- BlueStacks 5、夜神、逍遥、真机只由单元测试覆盖（本机未安装）。
- 雷电 9 实例里没有 QQ 阅读（登录需用户本人完成），未在雷电上跑任务。
- 广告、等级页广告、听书三类任务未在 1080×1920 下实机跑（都经 Maa 点击，由 OCR / 点击换算测试覆盖）。
- `scripts/package_release.py` 仍写死 MuMu 路径与旧版本号；本次 release 与上一版一样只发源码，未用它打包。
- 重新生成 interface.json 后控制器改名，MFAAvalonia 若记住了旧名称，首次打开可能需要重新选一次控制器。
**分支**：`claude/portability-adaptation-testing-5beafe`（基于本地 `master` `9b51fce`）。
**回滚**：`git log --oneline -S "可移植适配：多模拟器自动发现" -- CHANGELOG.md` 定位后 `git revert <hash>`（合并提交用 `git revert -m 1 <hash>`）。

---

## 2026-10-19 · 等级页广告：关闭「暂无可播视频」弹窗；「去浏览15秒」浏览弹层点「我要加速」领奖

**触发**：用户要求修正等级页广告遇到的问题。最近 4 次 `DailyLevelAdFlow` 失败（`runtime/records/daily_flows/`，均 exit 2）：`mfa_20261013_070802_e2cb29f0`、`mfa_20261014_104335_dd9a271c`、`mfa_20261016_144806_d665eacf`、`mfa_20261019_160110_39ab3243`；用 `runtime/logs/maafw.bak.2026.10.14-02.21.09.164.log`、`…10.14-06.02.36.744.log`、`…10.17-14.51.00.124.log`、`…10.19-11.20.12.811.log` 的 OCR 逐帧还原。这些运行用的是主目录当时检出的 `codex/restore-slide-captcha-20261018`（`0422420`），本分支以它为基线，不是 `master`。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| 赠币广告（10-14 04:44、10-19 10:01） | 点「立即领取」后弹出「暂无可播视频，点击下方广告领取本次激励奖励」，里面是淘宝广告卡（「立即领取」(292,849)、底部 X (336,1009)）。10-19：`LevelCoinAdNotStarted` 空等，`LevelClickCoinAdAgain` 点中广告卡的「立即领取」，跳到淘宝「正在跳转 / 下载淘宝」页，`LevelAdUnknownWait` 空等 20 次失败；10-14：等待后落到 `AdReturnStable` 失败 | 弹窗背后仍能读到「用户等级」，被当成“广告没拉起”；入口节点 `^立即领取$` 没有 ROI，弹窗里的同名按钮也会命中 | `scripts/run_task.py::_apply_level_no_video_overrides`（新增）：`LevelAdNoVideoDialog`（OCR「暂无可播视频」，DoNothing）→ `LevelAdNoVideoClose`（OCR 整框 X，ROI `[260,940,200,140]`，Click）→ 按 `LevelAfterAd` 锚点回原广告的后续核对（赠币 → 继续积分广告；积分 → 核对「今日已完成」/ 换广告重试）。插在所有含 `Level*AdNotStarted` / `AdScrollDownRepeat` / `LevelAdUnknownWait` / `LevelAdAccelerateWait` 的 next 里、验证码和挽留弹窗之后。`LevelClick{Coin,Points}Ad[Again]` 加 ROI `[460,120,260,1100]`，只认等级页右侧按钮列。不点弹窗里的广告 |
| 积分广告（10-13 01:09、10-16 08:49） | 「看小视频」后是「去浏览15秒 / 我要加速 / 免看此广告 / 可提前13秒领奖」浏览弹层；`LevelAdAccelerateWait` 自我循环 120 次（约 5.5 分钟）画面不变，然后 `LevelAdUnknownWait` 失败 | 10-11 的「只等待」方案依据的是「去体验9秒 … 9s后自动放弃继续播放视频内」版式；「去浏览15秒」版式没有自动放弃，弹层期间视频暂停（10-08 实机已证实）。等待节点自己的 next 里也没有任何出口 | `_apply_level_browse_accelerate_overrides`（新增，移植未合并的 `617359d` 做法，用户 2026-10-08 同意）：`LevelBrowseAccelerate`（OCR 整框「我要加速」，ROI `[150,650,420,160]`，点击后停 20 秒，max_hit 3）→ `LevelBrowseLandingBack`（返回键，max_hit 4）→ 已有的 `LevelAdRewardGrantedSkip` 点顶部「奖励已领取｜跳过」。插在每个含 `LevelAdAccelerateWait` 的 next（包括它自己的）中它的前面；次数用完回到原来的跳过 / 放弃 + 换广告路径。不认「我要加速领奖」（10-12 弹窗仍点「继续播放视频内容」），「Ns后自动放弃」版式仍只等待。落地页内不点任何内容 |

**改动文件**：`scripts/run_task.py`；`tests/test_level_ad_no_video_browse.py`（新增 36 项）；`tests/fixtures/level_ad_no_video_20261019.json`（新增，5 帧真实 OCR：10-19 等级页、10-19 / 10-14 弹窗、淘宝跳转页、10-16 浏览弹层）；`tests/fixtures/level_browse_ad_20261008.json`（取自 `617359d`）；`tests/test_level_ad_runtime_overrides.py`、`tests/test_level_points_accelerate_wait.py`（见下）；本日志。
**验证**：
- 新测试先写：去掉两个新函数的调用时 27 项失败、9 项通过（9 项是“自动放弃版式仍等待”和幂等的对照）；加上后 36 项全部通过。
- 改了 3 处写死旧行为的断言：`test_level_ad_overrides_recover_from_bottom_and_static_download_ads` 的精确 next 列表首位加上 `LevelAdNoVideoDialog`；`test_level_icon_click_swallowed_retries_without_global_ocr_x_close` 的“Level 节点不认 X”豁免加上 `LevelAdNoVideoClose`（与 `LevelPromoClose` 一样先确认弹窗文字、只看窄 ROI），并补断言 ROI；`test_level_points_accelerate_wait.py` 的只等待帧去掉 `offer_browse_15s`（该版式就是 10-13 / 10-16 失败的现场，现在改由新测试断言点加速）。
- 全量 `py -3.10 -m pytest`（本 worktree，复制本机 `dev/resource` pipeline，并以目录联接接入 `_backup_old_project_20260909_200716`）：698 passed、9 failed、2 skipped。9 项失败在改动前的基线上完全相同：`test_ad_round_regressions` ×2、`test_qqr27_ad_flow` ×1（已知 40 / 35 秒不一致），`test_issue13_legacy_timeout` ×4、`test_legacy_resource_isolation` ×2（worktree 环境）。
- 实机（命令行 `scripts/run_task.py --task DailyLevelAdFlow --timeout-minutes 30`，worktree 代码，覆盖写在独立副本 `runtime/legacy_resources/legacy-*`；MFA 空闲时运行，未点 GUI）：17:11:29–17:12:29，exit 0，`success: true`。17:11:53 积分广告是「我要加速 / 可提前13秒领奖 / 请勿中断浏览」弹层 → 点「我要加速」(406,737) → 停 20 秒 → 17:12:14 在落地页按返回 → 「恭喜提前获得奖励｜奖励已领取｜跳过」→ 点跳过 → 等级页「任务已完成，积分奖励发放中」，积分行同一行「今日已完成」(570,609)。
**未覆盖 / 遗留**：
- 「暂无可播视频」弹窗的关闭只由真实帧回放测试覆盖，**未实机触发**：本次等级页上没有赠币行（「赢10-99赠币」不在页面上，`LevelClickCoinAd` 未命中，直接做了积分广告）；赠币奖励今天是否已经到账未核实（10:02 那次误点进了淘宝页）。
- 关闭弹窗后不再重试赠币广告，当天赠币那一项可能拿不到；整条流程的成功条件仍只认积分行「今日已完成」。
- 已经误入第三方跳转页（「正在跳转 / 下载淘宝」）时仍只会等待，没有加返回键处理。
- 主目录 `G:\project_X` 11:59 被切回 `master`（`dcac7bf`，reflog 可查），而 MFA 在用的代码在 `codex/restore-slide-captcha-20261018`；`mfa/agent/main.py` 在 master 上不存在，当前 MFA 的 Agent 进程是切换前启动的。重启 GUI 前需要用户决定主目录检出哪个分支。本次未改动主目录。
- `617359d`（`claude/qqreadergui-startup-ad-recognition-61f65e`）的其余内容（阅读奖励导航合并）未移植。
**分支**：`claude/level-ad-no-video-20261019`（基于 `0422420`）；未推送、未合并。
**回滚**：`git log --oneline -S "关闭「暂无可播视频」弹窗" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-10-18 · 恢复滑块自动验证：启动 GUI 时清除继承的 manual 覆盖

**触发**：用户要求恢复被切为人工验证的滑块模块；今天 `gui_DailyAdFlow_20261018_113522.log`、`gui_DailyAdFlow_20261018_121713.log` 均以「未配置自动求解器，等待人工处理验证码」结束。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| GUI 启动环境 / 广告验证码守卫 | 本机配置 `captcha.solver=slide`，运行却使用人工守卫 | 现场 MFAAvalonia PID 86252 及 Agent PID 19516 均继承 `QQREADER_CAPTCHA_SOLVER=manual`；配置加载器按约定用环境变量覆盖文件。用户和系统注册表均未设置该变量，属于进程链残留 | `启动QQReaderGUI.cmd` 初始化时清除该变量，GUI 与子进程按本机配置选用原有自动滑块求解与求解后复核；不改求解算法、CLI 的环境覆盖机制或人工兜底 |

**改动文件**：`启动QQReaderGUI.cmd`、`tests/test_mfa_agent_entry.py`、`CHANGELOG.md`。
**验证**：新增回归先执行真实启动初始化批处理，复现 `manual ManualCaptchaGuard`；修复后验证实际广告任务装配为 `slide VerifyingCaptchaGuard`。相关测试 47 passed、1 skipped；加强任务装配断言后入口测试 11 passed。全量 672 passed、4 failed、1 skipped（13.97s）：`test_ad_round_regressions` 两项及 `test_qqr27_ad_flow` 一项为已有 40 秒断言与 35 秒实现不一致；`test_issue15_reward_nav` 一项缺少开工时已删除的 `runtime/screenshots/ad_watch/captcha_now.png`。`git diff --check` 通过。空闲旧 GUI 正常关闭后经正式启动器重启；读取新 GUI PID 10496、Agent PID 47192 的实际环境，确认覆盖变量均不存在。
**未覆盖 / 遗留**：未运行广告或真实滑块求解；配置与入口已恢复不代表验证码通过。保留原截图删除与未跟踪快捷方式，不提交。未修改全局环境。
**分支**：`codex/restore-slide-captcha-20261018`；仅本地提交，不推送、不合并。
**回滚**：用 `git log --oneline -S "恢复滑块自动验证：启动 GUI 时清除继承的 manual 覆盖" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-10-12 · 广告「获得加速机会」弹窗：点「继续播放视频内容」，再多等 30 秒

**触发**：用户贴出新广告形式截图（「获得加速机会！去看9秒可直接拿奖励 / 我要加速领奖 / 继续播放视频内容」，顶部「还需观看28秒领奖｜跳过」），要求点下方文字继续看视频，并在原等待基础上延长 30 秒。对应今天三次 `DailyAdFlow` 失败：`mfa_20261012_234639_db3a34bc`、`mfa_20261012_235405_fefbb57d`、`mfa_20261012_235812_fc36744e`（`runtime/records/DailyAdFlow_20261012_175124_078016.json`、`…_175726_088040.json`、`…_180749_747125.json`，均为 `ad_exit_unconfirmed`）。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| `DailyAdFlow` / `qqreader/tasks/ad.py::AdTaskAdapter.advance` | 记录里三次都是：进广告 → `点击特征 ad_ocr_accelerate` → 等 35 秒 → 点「跳过」→ 点 (48,70) → 返回键 → 20 秒未回奖励页，`ad_exit_unconfirmed`。失败截图里弹窗仍在，倒计时停在 27 / 28 秒；17:57 那次停在第三方应用详情页（「去浏览9秒 / 立即下载」） | 弹窗按钮「我要加速领奖」包含旧文案「我要加速」（`ad_ocr_accelerate`），被当成加速按钮点掉，跳去第三方应用；弹窗挂着时倒计时不走，之后怎么退都看不满 | 新增 `_handle_accelerate_offer`，排在广告播放分支最前：同屏有「加速机会 / 加速领奖 / 可直接拿奖励」且有「继续播放视频内容」时点后者（新特征 `ad_ocr_continue_video`，「10s后自动放弃继续播放视频内容」同样命中）；重新截图确认弹窗消失后等 30 秒，本轮还没做过 35 秒初始等待时合并成 65 秒；弹窗还在就再点，不开始计时。有「我要加速领奖」但小字没被 OCR 读到时只等 2 秒重看，不点加速。同屏有「坚持退出 / 放弃奖励」时不介入，仍走原退出分支。回到奖励页时清掉未用的加长等待 |
| 同上 | 这类广告底部写着「上滑或点击 跳转至详情页或第三方应用」，命中直播间文案「上滑或点击」，会跳过 35 秒初始等待并每 5 秒下滑一次 | `live_texts` 里的「上滑或点击」对这类倒计时视频不成立 | 新增 `_has_reward_countdown`：顶部是「还需观看N秒领奖」时不按直播间处理（先等 35 秒，不下滑） |
| `DailyLevelAdFlow` / `scripts/run_task.py::_apply_level_accelerate_wait_overrides` | 用同一批真实帧离线回放等级广告 pipeline：弹窗帧和「还需观看28秒领奖｜跳过」帧的首个命中都是 `AdSkipBrowseOffer`（点顶部「跳过」，会弹退出确认） | `LevelAdAccelerateWait` 的正则不认「还需观看N秒领奖」；pipeline 里没有「继续播放视频内容」节点 | 等待正则加 `还需观看\d+秒领奖`；新增 `LevelAdAccelerateDecline`（OCR「继续播放视频内容」，ROI `[100,600,520,500]`，Click，post_delay 30000，max_hit 3），插在各 next 列表的 `LevelAdAccelerateWait` 之前；新增 `LevelAdRewardGrantedSkip`（`AdSkipBrowseOffer` 的副本，只认「奖励已领取/发放…跳过」）排在它前面，10-04「恭喜提前获得奖励」弹窗仍按原样点顶部跳过退出。只在等级广告的临时 pipeline 生效，不改 `dev/resource` |

**改动文件**：`qqreader/tasks/ad.py`、`qqreader/page/feature_keys.py`、`scripts/run_task.py`、`tests/test_ad_accelerate_offer.py`（新增，30 项）、`tests/fixtures/ad_accelerate_offer_ocr_frames.json`（新增，5 帧）、`CHANGELOG.md`。
**验证**：
- 样本：今天失败现场的 5 张真机截图（`runtime/screenshots/20261012/DailyAdFlow_20261012_*`），用本机 `dev/resource` 的 Maa OCR 离线识别（自定义控制器喂图）得到原始文字框，未手改。
- 新测试先写：修复前 `DailyAdFlow` 部分 11 项中 9 项失败（另 2 项是「行为不变」的对照）；修复后 `tests/test_ad_accelerate_offer.py` 30 项全部通过。等级广告部分的测试是实现后补的，修复前的走向见上表的离线回放。
- 全量 `py -3.10 -m pytest`：671 passed、3 failed、2 skipped。3 项失败在基线提交 `219d431` 上同样失败（`test_ad_round_regressions` ×2、`test_qqr27_ad_flow` ×1，期望 40 秒初始等待，代码是 35 秒）。
- **未实机验证**：没有跑任何任务。
**未覆盖 / 遗留**：
- 点「继续播放视频内容」后弹窗是否立即消失、30 秒后顶部变成什么文案（推测是 10-04 同款 SDK 的「奖励已领取｜跳过」，已有出口处理）都没有实机帧，只由单元测试覆盖。
- 等级广告今天的失败（`mfa_20261012_235125_daa0d570`，exit 2）没有证据是这个弹窗引起的，本次只按离线回放补了同款处理，未实机触发。
- 已经误点进第三方详情页的状态（17:57 那帧）没有单独处理：修复后不会再走到；等级广告在该帧上会等待。
- 交接检查把残留广告的「还需观看27秒领奖｜跳过」当开屏点「跳过」再「坚持退出」，能清场，未改。
- 本分支由 `dcac7bf`（与本地 `master` 相同）快进到主目录在用的 `codex/reading-game-log-fix-20261004`（`219d431`）后再改，不是基于 `master`。Linear 连接失败，未查到对应 Issue 编号。
**分支**：`claude/new-ad-format-extended-wait-bfc693`；未推送、未合并。
**回滚**：`git log --oneline -S "获得加速机会」弹窗：点「继续播放视频内容" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-10-12 · 启动 MFAAvalonia 前写入「新手教程已完成」，新 GUI 不再每次弹教程

**触发**：用户反馈每次打开新 GUI（MFAAvalonia）都会弹出新手教程，要求关闭并测试。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| GUI 启动器 / MFAAvalonia | 打开新的 MFAAvalonia 时，主界面蒙上遮罩并弹出「工具栏概览 … 下一步」新手教程 | MFAAvalonia 启动时读 `mfa/config/config.json` 的 `UI.HasCompletedFirstUseTutorial`，不是 `true` 就弹教程，只有把教程走完才自己写入（上游 `RootViewContent.axaml.cs` / `TeachingTipOverlay.axaml.cs`）。`mfa/config/` 被 `.gitignore` 忽略，每一份新的 MFA 目录（重新解压、新 worktree、从别处拷贝程序文件）都没有这个键：主目录 `mfa/config` 是 2026-10-12 09:19 才新建的（`mfa/logs/log-20261012.log`：「检测到仅包含临时启动数据的 default 实例文件，按首次启动处理」） | 新增 `qqreader/mfa/first_use.py::ensure_tutorial_completed`：配置不存在则新建只含该键的 `config.json`；已存在则只补这一个键、其余键原样保留；已是 `true` 不改写；读不懂的配置不覆盖。`启动QQReaderGUI.cmd` 6a 段在 `start … MFAAvalonia.exe` 之前调用 `%PYEXE% -m qqreader.mfa.first_use "%ROOT%mfa"`（任何情况返回 0，不拦启动） |

**改动文件**：`qqreader/mfa/first_use.py`（新增）、`启动QQReaderGUI.cmd`、`tests/test_mfa_first_use.py`（新增，9 项）、`CHANGELOG.md`。
**验证**：
- 单元测试：`tests/test_mfa_first_use.py` 9 项 + 其余 3 个 MFA 测试文件共 58 项全部通过。
- 全量 `py -3.10 -m pytest`（本 worktree）：605 项，549 passed、55 failed、1 skipped。失败与本次改动无关：46 项是 worktree 里没有未入库的 `dev/resource/pipeline/qq_reader_trial.json`（`FileNotFoundError`），其余 9 项是已知失败（`test_ad_round_regressions` ×2、`test_issue13_legacy_timeout` ×4、`test_legacy_resource_isolation` ×2、`test_qqr27_ad_flow` ×1）。
- GUI 实机（MFAAvalonia v2.16.2，把主目录 `mfa` 的程序文件拷到本 worktree 的 `mfa/`，不带 `config/`，按进程 ID 截取窗口）：
  - 对照（不经启动器直接运行 `MFAAvalonia.exe`）：弹出「工具栏概览」教程，`config.json` 里没有该键 —— 复现。
  - 修复后（删掉 `config/` 等运行时目录，运行 `启动QQReaderGUI.cmd`）：启动器输出「已关闭 MFAAvalonia 新手教程」，窗口无教程无遮罩，两个 preset 实例「正式每日」「1 分钟试跑」照常创建，实时视图连上模拟器；MFA 随后写回的 `config.json` 仍保留 `"UI.HasCompletedFirstUseTutorial": true`。
  - 测试用的 MFA 进程按进程 ID 结束，拷入的程序文件已删除；未动主目录正在运行的 MFAAvalonia。
**未覆盖 / 遗留**：未跑任何 QQ 阅读任务（本次不涉及任务流程）。绕过启动器直接双击 `mfa\MFAAvalonia.exe` 打开一份全新目录时仍会弹教程。主目录当前 `mfa/config/config.json` 已是 `true`（15:38 写入），本修复合入前它也不会再弹。MFAAvalonia 首次启动会自动执行一次「启动任务」（连接模拟器、拉起 Agent），这是它原有行为，未改。
**分支**：`claude/tutorial-popup-issue-81925d`（基于 `6b11044`）；未推送、未合并。主目录工作区对 `启动QQReaderGUI.cmd` 另有未提交改动（去掉 `chcp 65001`），与本次改动不在同一行。
**回滚**：`git log --oneline -S "新 GUI 不再每次弹教程" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-10-11 · MFAAvalonia GUI 入口统一

**触发**：用户要求 ProjectX 的 GUI 启动入口默认使用新 GUI。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| GUI 启动器 | 调试入口仍直接打开 Tkinter；主入口含长批处理不应使用的 `chcp 65001` | 两个入口未统一到 MFAAvalonia，且改码页可能使长 `.cmd` 标签定位错位 | 主入口默认 MFAAvalonia；调试 GUI 模式转调主入口并识别 MFAAvalonia 进程；移除 `chcp 65001`，保留 `classic` 旧 GUI 选项 |

**改动文件**：`启动QQReaderGUI.cmd`、`调试QQReader.cmd`、`tests/test_mfa_agent_entry.py`。
**验证**：相关 4 个测试文件通过；启动器 CRLF/编码/默认路由静态检查通过；配置 Python 3.10.11、MaaFw 5.12.3 可用。
**未覆盖 / 遗留**：未执行 `.cmd`、未启动模拟器、未做 QQReader 实机或 GUI 窗口验收；仅验证了启动路径与依赖。
**分支**：`codex/reading-game-log-fix-20261004`，已快进到 `6b11044`；本次启动器/测试改动未提交、未推送。
**回滚**：只回滚上述三个文件的本次差异；分支快进回退需先确认保护方案，`stash@{0}` 保留作原工作区备份。

---

## 2026-10-11 · AGENTS.md：写入 QQReader 项目约定，限定只在本目录修改

**触发**：用户要求把 QQReader 的记忆合并进项目文件夹并写入 AGENTS.md，同时规定每次修改只在 `G:\project_X` 内进行。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| AGENTS.md「Project overview」 | 没有写明「每次修改只在本目录进行」 | 约定只在对话和记忆里，没有写进仓库规则 | 新增一条：所有 agent 每次修改只在 `G:\project_X` 内进行；目录外的文件（包括 `Documents\Codex`、其他项目和全局配置）不改 |
| AGENTS.md「Project overview」Linear 一行 | 没有写明问题单不用 GitHub Issues | 同上 | 补充「问题单只用 Linear，不用 GitHub Issues」 |

**改动文件**：`AGENTS.md`；`CHANGELOG.md`
**验证**：未跑测试，原因：仅文档。AGENTS.md 的 diff 只有 1 行新增、1 行改动（已核对）；两个文件保持 CRLF。
**未覆盖 / 遗留**：无。实机：不适用。
**分支**：未提交。工作区仍在 `codex/reading-game-log-fix-20261004`（HEAD ade4c81），与等级广告修复一起等待用户决定提交。
**回滚**：删除 AGENTS.md 中新增的那一条，把 Linear 那一行改回原文，并删除本条 CHANGELOG。

---

## 2026-10-11 · 等级页积分广告：浏览加速只等待，不点顶部「跳过」

**触发**：每日完整运行 `daily_20261011_011921_3cef26ce`（6/6 成功；06 DailyLevelAdFlow 本轮成功，但没有遇到浏览加速页，见下方验证）。前两次失败的证据：`runtime/records/daily_flows/daily_20261010_213243_c06840c8.json` 的 05 DailyLevelAdFlow（FAILED，exit 2）；`daily_20261011_005954_9f1bf254.json` 的 01 DailyLevelAdFlow-1（FAILED，exit 2，2m12s）。maafw 日志 `runtime/logs/maafw.log` 中 2026-10-10 17:23–17:25（本机 UTC+2）为同一失败现场。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| DailyLevelAdFlow `LevelClickPointsAd` 及含 `AdSkipBrowseOffer` 的广告 next 列表 | 看小视频进入「去体验9秒可立即领奖｜跳过」，点顶部「跳过」→「确定要退出吗？」→ 挽留弹窗「继续观看」3 次后仍回到弹窗 → 「坚持退出」放弃奖励；`LevelVerifyPointsScroll` 5 次后 20.8 秒超时失败 | 顶部「跳过」在浏览加速页上会退出广告，而加速约 9–15 秒后会自动放弃并在视频内继续播放（「9s后自动放弃继续播放视频内」），「27s｜跳过」倒计时走完即发奖；原 next 中 `AdSkipBrowseOffer` 先于一切等待命中。离线用 10-10 实机 OCR 框（8 帧）重放：原 pipeline 有 7 帧先命中 `AdSkipBrowseOffer`（5 个浏览加速或跳过倒计时帧、1 个挽留弹窗帧、1 个退出确认帧）；新 pipeline 分别命中 `LevelAdAccelerateWait`（5 帧）、`LevelAdRetentionContinue`（1 帧）、`LevelAdRetentionGiveUp`（1 帧）；倒计时帧仍为 `AdCountdown` | `scripts/run_task.py` 新增 `_apply_level_accelerate_wait_overrides`，只在 `DailyLevelAdFlow` 的临时 pipeline 生效：新增 `LevelAdAccelerateWait`（OCR 命中 `去体验N秒｜去浏览N秒｜Ns后自动放弃｜可提前N秒领奖｜Ns｜跳过`，`DoNothing`，post_delay 1.5 秒，max_hit 120），插在含 `AdSkipBrowseOffer` 的 next 列表中该节点之前；验证码与挽留弹窗节点提到最前。不改 `dev/resource` 源文件，不改 `DailyAdFlow`。 |

**改动文件**：`scripts/run_task.py`；`tests/test_level_points_accelerate_wait.py`（新增）；`tests/fixtures/level_points_accelerate_ocr_frames.json`（新增，8 帧真实 OCR 框）；`CHANGELOG.md`
**验证**：
- 单元测试：`tests/test_level_points_accelerate_wait.py` 40 项（真实 pipeline + 实机 OCR 框）；`test_qqr54_level_ad_retention.py`、`test_level_ad_runtime_overrides.py`、`test_ad_failures_20261004.py` 等等级广告相关用例全部通过。
- 全量离线 pytest（Linux 容器，未装 tkinter）：507 passed，10 failed，4 个收集错误。失败集合与改动前相同（`test_ad_round_regressions`、`test_issue13_legacy_timeout`、`test_issue15_reward_nav`、`test_legacy_resource_isolation`、`test_qqr27_ad_flow`），4 个收集错误为 GUI 模块缺 tkinter。Windows 侧未跑 pytest（需要终端），请用 `调试QQReader.cmd test` 复核。
- 实机（修复前的原代码）：完整轮 `daily_20261011_011921_3cef26ce` 6/6 SUCCEEDED：01、02 DailyReadingFlow，03 DailyGameFlow，04 DailyAdFlow（12/12，19:02:07–19:13:11 UTC），05 DailyAudiobookFlow（35 分钟，19:13:22–19:49:05 UTC），06 DailyLevelAdFlow（19:49:16–19:50:59 UTC，1 分 42 秒，「奖励已发放」「今日已完成」）。06 本轮看的是「观看N秒，可获得奖励」视频（倒计时 28 → 2 秒），之后显示「暂无更多内容，奖励已发放」，没有出现「去体验N秒｜跳过」，所以浏览加速分支没有在实机触发。
- 修复后离线路由对比：同一轮 06 的 10 帧广告 OCR（`maafw.log` 21:49:16–21:51:00 UTC+2）上，原 pipeline 与新 pipeline 对 271 个含 next 列表的节点，首个命中节点 0 处差异（临时脚本，未入库）。
- 修复后的实机验证：待遇到浏览加速广告时确认（`LevelAdAccelerateWait` 命中、不点顶部「跳过」、奖励发放）。
**未覆盖 / 遗留**：
- 浏览加速页的「跳过」在倒计时结束后变为裸「跳过」，若与奖励弹窗同帧出现仍可能被点到；实机验证会观察这一点。
- 积分行「今日已完成」的 ROI（520,500,180,300）是否与放大后的页面位置一致，需要以实机结果确认。
- 退出确认框（只有「坚持退出」，背景残留「去体验N秒｜跳过」）原先先命中 `AdSkipBrowseOffer`，现在直接命中 `LevelAdRetentionGiveUp` 并点「坚持退出」放弃本条广告。正常流程不应再出现这个框，因为不再点跳过。
- 赠币广告 `LevelClickCoinAd` 的 next 列表不含 `AdSkipBrowseOffer`，本次不改其行为。
**分支**：未提交。改动在 `codex/reading-game-log-fix-20261004` 的工作区（HEAD ade4c81）；若提交，建议新建 `claude/level-points-accelerate-20261011`。
**回滚**：`git revert <提交 hash>`；或删除 `_apply_level_accelerate_wait_overrides` 的调用行
---

## 2026-10-06 · 接入 MFAAvalonia 作为日常 GUI

**触发**：用户要求按 MaaFramework 官方通用 GUI 第一个 MFAAvalonia 重构 GUI（设计见 `docs/superpowers/` 下 MFAAvalonia 接入设计与实施计划）。本条随后续任务继续补充。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| `qqreader/mfa/agent_action.py`（新增） | MFAAvalonia 只能通过 Agent 自定义动作调用 Python，旧 Tk GUI 的串行逻辑无法复用 | 交接检查、子进程管理、记录写在 Tk 界面类 `qqreader/gui/app.py` 里 | 新增纯逻辑模块（不导入 `maa`）：`ACTION_NAME = "QQReaderRunTask"`；`parse_param` 解析 JSON 参数并按任务目录 `TaskSettingField.normalize` 规整（未知任务 / 未知键 / 非法值抛中文 `ValueError`，`count` 忽略，交给 MFA 的 `repeat_count`）；`TaskRunner.run` 加载本机配置 → 单步 `DailyFlowRun`（run_id 前缀 `mfa_`）→ `HandoffCheck` 子进程 → `apply_handoff` → `scripts/run_task.py` 子进程 → `complete_current` → 写 `records/daily_flows/`；0.5 秒轮询，停止时只按本动作启动的 PID `taskkill /T /F`，返回 13；交接 / 任务退出 10 时 `exit_code=10`、消息含 `BLOCKED_BY_CAPTCHA`；子进程输出按 UTF-8（errors=replace）逐行转发 |
| `qqreader/mfa/interface.py`、`scripts/build_mfa_interface.py`（新增）；生成 `mfa/interface.json`、`mfa/resource/pipeline/qqreader.json` | MFAAvalonia 需要 PI V2 `interface.json` 和 pipeline 才能列出任务 | 任务与参数只定义在任务目录 `DEFAULT_TASK_CATALOG` | 由任务目录生成：每个任务一个节点 `QQR_<key>`（`Custom` 动作 `QQReaderRunTask`，`custom_action_param` = `task` + 各字段默认值，不含 `count`）；有 `count` 的任务 `repeatable: true`、`repeat_count` 取默认次数。**每个任务只生成一个 `input` 选项 `<key>.settings`**：PI V2 文档「资源覆盖」规定同名节点只按顶层键替换、内部不合并，MFAAvalonia v2.16.2 也是把各选项覆盖逐个交给 MaaFramework（`MaaToken.Merge` 只追加），多个选项写同一 `custom_action_param` 会互相覆盖，因此覆盖里写全 `task` 和全部字段。`pipeline_type` 只有 `string` / `int` / `bool`（文档与 `interface.schema.json` 均无 `double`）：小数字段用 `string`（Agent 侧 `normalize` 转浮点），布尔字段用 `bool` 输入并校验 `^(true|false)$`（不用 switch，原因同上）。保留 `preset`「正式每日」「1 分钟试跑」（PI v2.3.0，MFA v2.16.2 `MaaInterfacePreset` 支持）。`scripts/build_mfa_interface.py --check` 只比对，不一致退出码 1；版本号取 `pyproject.toml` |
| `mfa/agent/main.py`（新增） | MFAAvalonia 按 `interface.json` 的 `agent` 段启动 `python -X utf8 ./agent/main.py <socket_id>`，需要注册 `QQReaderRunTask` 的 Agent 入口 | — | 仓库根（`parents[2]`）插入 `sys.path`；`check_runtime()` 检查 `maa` 可导入且 `importlib.metadata.version("MaaFw") == "5.12.3"`，否则打印中文消息与 `python -m pip install "MaaFw==5.12.3"` 并 `exit 2`；通过后才 `import maa`（API 按 MaaFramework v5.12.3 `source/binding/Python/maa/` 核对）。动作 `run`：`parse_param` 失败返回 `success=False`；`TaskRunner(repo_root, configs/qqreader.local.json, is_stopping=context.tasker.stopping)`；退出码 10（BLOCKED_BY_CAPTCHA）时 `context.tasker.post_stop()` 停掉整个队列；`Toolkit.init_option(mfa/)` → `AgentServer.start_up(sys.argv[-1])` / `join` / `shut_down` |
| `qqreader/mfa/agent_action.py::parse_param` | MFA 输入框未被替换时会把占位符原样（如 `{cover_image}`）传进参数，按非法值报错或当成书名 | 未区分占位符与真实取值 | 整串匹配 `^\{[A-Za-z_][A-Za-z0-9_]*\}$` 的字符串按缺省处理，取字段默认值（例如听书 `minutes="{minutes}"` → 35.0，`cover_image="{cover_image}"` → `""`）；带其它字符的（如 `{宇智波}/火影`）原样保留 |
| `启动QQReaderGUI.cmd`（第 6 段） | 日常入口仍是旧 Tk GUI | — | 步骤 1–5 不变；默认打开 MFAAvalonia：`mfa\MFAAvalonia.exe` 不存在时提示从 Releases 下载 v2.16.2 win-x64 解压到 `mfa\`（或用 `classic`），`pause` 后 `exit /b 3`；`%PYEXE% -c "import maa"` 失败时提示 `%PYEXE% -m pip install "MaaFw==5.12.3"`，`exit /b 4`；否则把该 Python 所在目录前置到 `PATH`（MFA 以 `python` 启动 Agent），`PYTHONPATH=仓库根`，`start "" /D mfa MFAAvalonia.exe`。`启动QQReaderGUI.cmd classic` 走原 Tk 启动（有本机配置时带 `--config`）。注意：原来「带任意参数时原样转给 `qqreader.gui`」的用法取消，非 `classic` 参数一律打开 MFA |
| `.gitignore`、`pyproject.toml` | MFA 程序文件、`config/`、`debug/`、`logs/` 不应入库；MaaFw 依赖未声明 | — | `.gitignore` 增加 `mfa/*`、`!mfa/interface.json`、`!mfa/resource/`、`!mfa/agent/`；`pyproject.toml` 增加可选依赖 `mfa = ["MaaFw==5.12.3"]`，核心 `dependencies = []` 不变 |
| `qqreader/tasks/reading_reward.py::_open_reward_page`（原有缺陷） | 实机 `mfa_20261006_205809_33602f6e`（第 2 次 1 分钟阅读）exit 2：「[post-task] 阅读奖励领取异常：无法从当前页面进入阅读奖励页」。书架点「本周阅读时长/领赠币>」5 秒后，奖励网页仍在加载，OCR 只读到 `8:59`/`O`/`2`/`0` 四个框 | 点击入口后把加载中/空白帧当成“页面不对”直接按返回（keycode 4），取消了正在加载的奖励页，回书架再点、再按返回，7 轮耗尽；第 1 次运行只是碰巧在第 3 次点击约 6 秒内加载完 | 拆出 `_find_reward_entry`；新增 `_wait_for_reward_page`：点击入口后每 1.5 秒重新截图，最多 15 秒（`_open_reward_page(load_wait_seconds=15.0, poll_seconds=1.5)` 可注入）。看到奖励页 → 返回；点击 5 秒稳定期（`settle_seconds=5.0`，与旧代码点击后等 5 秒一致）之后仍看到入口才算点击没生效 → 回外层重点（计入 7 轮），稳定期内的书架帧只继续轮询，避免页面切换慢时重点打开两层奖励页（之后 `_refresh_reward_page` 按返回会落到旧奖励页）；加载中/空白/未知帧 → 继续等待，不按返回。等满仍无奖励页才按返回再判定；点击前的帧不是书架也不是奖励页时仍按返回（原逻辑）。最后一轮点击后等到奖励页时返回该页，不再误报失败；轮询间隔取非负值（≥0.01 秒），睡眠与次数计算用同一个值。最坏耗时（每轮都等满 15 秒）约 7×(15 秒 + 10 次截图 OCR + 1.2 秒) ≈ 2～3 分钟 |
| `qqreader/mfa/agent_action.py::TaskRunner._child_env` | 实机 `mfa_20261006_210156_c258e537`：DailyGameFlow 的输出全部在结束时（15:04:12.4）一次性出现在 MFA 日志，运行中看不到进度 | 子进程 stdout 是管道，Python 默认块缓冲；子进程环境只设了 `PYTHONUTF8` / `PYTHONIOENCODING` / `PYTHONPATH` | 交接检查与任务两个子进程的环境都加 `PYTHONUNBUFFERED=1` |
| `.gitignore`、`mfa/agent/main.py`（整支复审修正） | MFA 运行时写入 `mfa/resource/mfa_layout.json`（界面布局），因 `!mfa/resource/` 被反忽略而长期显示为未跟踪；验证码停队列分支没有任何测试；动作里除参数 `ValueError` 外的异常会直接抛给 MaaFw | `.gitignore` 只按目录反忽略；动作类在 `main()` 内注册，无法注入伪造 `maa` 测试；`run` 只捕获 `ValueError` | `.gitignore` 在 `!mfa/agent/` 之后加 `mfa/resource/mfa_layout.json`；`main.py` 把导入 `maa` 与注册动作抽成 `register_actions()`（返回动作类，`main()` 调用它，行为不变）；`QQReaderRunTask.run` 外层加 `except Exception`，用 `_log` 打印「[QQReader] 动作异常：」+ traceback 并返回 `success=False`（原逻辑移到 `_run`） |

**改动文件**：`qqreader/mfa/__init__.py`、`qqreader/mfa/agent_action.py`、`tests/test_mfa_agent_action.py`、`qqreader/mfa/interface.py`、`scripts/build_mfa_interface.py`、`mfa/interface.json`、`mfa/resource/pipeline/qqreader.json`、`tests/test_mfa_interface.py`（新增）、`mfa/agent/main.py`、`tests/test_mfa_agent_entry.py`（新增；复审后补伪造 `maa` 模块的动作测试与 `mfa_layout.json` 忽略断言）、`启动QQReaderGUI.cmd`、`.gitignore`、`pyproject.toml`、`qqreader/tasks/reading_reward.py`、`tests/test_reading_reward_claim.py`、`tests/fixtures/reading_reward_open_frames.json`（新增，实机 OCR 帧原样：书架 1 帧、加载中 3 帧、奖励页 1 帧）；复审修正再改 `.gitignore`、`mfa/agent/main.py`、`tests/test_mfa_agent_entry.py`、`README.md`（MFA 需 .NET 运行库的说明）；本日志。
**验证**：`py -3.10 -m pytest tests/test_mfa_agent_action.py`：21 passed（实现前收集即 `ModuleNotFoundError`）。全量 `py -3.10 -m pytest`：459 passed、21 failed、2 skipped；不含新文件时为 438 passed、21 failed，失败项完全相同（4 项为 master 已知失败；其余 17 项是本 worktree 缺少被 .gitignore 忽略的 `dev/resource/pipeline/*.json` 与 `_backup_old_project_*` 目录），无新增失败。生成器：`py -3.10 -m pytest tests/test_mfa_interface.py`：16 passed（实现前收集即 `ModuleNotFoundError`）；`py -3.10 scripts/build_mfa_interface.py --check` 退出码 0；全量 475 passed、21 failed、2 skipped，失败项与上面相同。Agent 入口 / 启动脚本 / 占位符：先写 `tests/test_mfa_agent_entry.py`（6 项）与 `test_unreplaced_placeholder_uses_default` 等 2 项，实现前 7 项失败（缺 `main.py`、启动脚本无 `classic`、`.gitignore` 未忽略 `mfa/MFAAvalonia.exe`、占位符报 `could not convert string to float`）；实现后 `tests/test_mfa_agent_entry.py tests/test_mfa_agent_action.py tests/test_mfa_interface.py` 45 passed；全量 483 passed、21 failed、2 skipped，失败项与上面相同。`git check-ignore --no-index`：`mfa/interface.json`、`mfa/agent/main.py`、`mfa/resource/pipeline/qqreader.json` 不忽略，`mfa/MFAAvalonia.exe`、`mfa/config/*`、`mfa/agent/__pycache__/*` 忽略。启动脚本第 6 段在临时目录单独试跑：缺 exe 时 exit 3、缺 MaaFw 时 exit 4（提示 `py -3.10 -m pip install "MaaFw==5.12.3"`）、`classic` 走 Tk 启动行、`PYDIR` 正确前置到 `PATH`；未实际启动 MFAAvalonia（本机未安装 MaaFw、`mfa/` 下无 MFAAvalonia 程序）。

阅读奖励页加载等待：先加 `tests/test_reading_reward_claim.py` 3 项（`test_open_reward_page_waits_while_page_loading`、`test_open_reward_page_reclicks_when_still_on_shelf`、`test_open_reward_page_backs_out_after_wait_expires`，数据为真实 OCR 帧），修复前 3 项全失败（前两项点击后按了返回，第三项不支持等待参数）；修复后该文件 9 passed；全量 504 passed、4 failed（master 已知 4 项广告相关失败）、1 skipped，无新增失败。复审后补“稳定期”：改 `test_open_reward_page_reclicks_when_still_on_shelf`（书架持续到 6 秒才重点），新增 `test_open_reward_page_shelf_seen_briefly_then_loads_clicks_once`、`test_open_reward_page_returns_reward_seen_on_last_attempt`、`test_open_reward_page_negative_poll_does_not_sleep_negative`，修改前 4 项失败（多点 3 次 / 多点 1 次 / 最后一轮误报 RuntimeError / 睡眠负数），修改后该文件 12 passed；全量 508 passed、4 failed（已知）、1 skipped。

MFAAvalonia 实机冒烟（2026-10-06）：`mfa_20261006_205538_7b15d865` 阅读#1 成功；`mfa_20261006_205809_33602f6e` 阅读#2 exit 2（即上表阅读奖励页缺陷，修复前代码）；`mfa_20261006_210010_77680a4a` 听书 成功；`mfa_20261006_210156_c258e537` 游戏 成功（但游戏子进程输出在结束时才一次性出现在 MFA 日志，见上表 `_child_env` 一行）。

子进程输出不缓冲：先加 `tests/test_mfa_agent_action.py::test_child_env_is_unbuffered`，修复前 `KeyError: 'PYTHONUNBUFFERED'`；修复后该文件 24 passed；全量 505 passed、4 failed（master 已知）、1 skipped（Tk 相关测试偶发因 `tk.tcl` 找不到而多跳过 1 项，与本改动无关）。

全量（本次最终）：`py -3.10 -m pytest -q` 508 passed、4 failed（master 已知失败，与本次改动无关：`test_each_ad_round_has_its_own_initial_wait`、`test_live_exit_attempt_does_not_restart_eight_swipe_cycle`、`test_live_snap_detects_saved_png_not_raw_screenshot_data`、`test_ad_play_waits_40_seconds_before_handling_buttons`）、1 skipped。

MFAAvalonia 实机冒烟 #1（用户在 MFA 里点击，worktree 代码，修复前）：`mfa_20261006_205538_7b15d865` 阅读#1 成功；`mfa_20261006_205809_33602f6e` 阅读#2 exit 2（`reading_reward` 奖励页加载中按返回缺陷，见上表）；`mfa_20261006_210010_77680a4a` 听书 成功；`mfa_20261006_210156_c258e537` 游戏 成功（输出有缓冲，日志结束时才一次性显示，见上表 `_child_env` 一行，当时未修）。

MFAAvalonia 实机冒烟 #2（修复 83c382c / 54715b2 / ff08660 之后重跑）：`mfa_20261006_221931_af0f2959` 阅读#1 成功；`mfa_20261006_222128_9bad8f41` 阅读#2 成功（两次均正常进入奖励页并确认「已领取」，验证了奖励页加载等待修复）；`mfa_20261006_222318_a6e42f2e` 游戏 成功，日志实时显示（验证了子进程不缓冲修复；结尾整段仍是 `run_task.py` 设计上固定输出的最近 60 条诊断摘要，非缓冲残留）；听书 #2 未重跑（#1 已成功，按规则不重复验证已通过任务）。

整支复审修正：先在 `tests/test_mfa_agent_entry.py` 加 `test_captcha_exit_stops_whole_queue`、`test_success_exit_does_not_stop_queue`、`test_unexpected_exception_returns_failure` 与 `mfa_layout.json` 忽略断言，修改前 4 项失败（无 `register_actions`、未忽略）；抽出 `register_actions()` 后前两项通过、异常项仍抛 `RuntimeError: boom`；加外层兜底与 `.gitignore` 行后该文件 9 passed，`git status --short` 不再列出 `mfa/resource/mfa_layout.json`；用本机真实 MaaFw 5.12.3 加载 `main.py` 调 `register_actions()`，动作类正常继承 `maa.custom_action.CustomAction`；`py -3.10 scripts/build_mfa_interface.py --check` 退出码 0；全量 511 passed、4 failed（同上 master 已知 4 项）、1 skipped。

旧 Tk GUI：`python -m qqreader.gui --config ...` 启动后 8 秒内无异常，按 PID 结束，确认未因本次改动（新增 `classic` 分支）破坏旧入口；`启动QQReaderGUI.cmd classic` 整个脚本未实机跑过，`classic` 分支目前只由抽出的脚本片段测试覆盖。
**未覆盖 / 遗留**：验证码阻塞 → `context.tasker.post_stop()` 整队列停止只由单元测试覆盖（`tests/test_mfa_agent_entry.py` 用伪造 `maa` 模块注册动作，退出码 10 时 `post_stop` 调用 1 次且判失败、退出码 0 时不调用），未实机触发验证码；直接关闭 MFA 窗口（而不是点「停止」）时，`run_task.py` 子进程可能继续运行，未验证，后续可用 Windows Job Object（kill-on-close）兜底；启动脚本的 `%PYEXE%` 路径含空格时不支持（沿用原有写法）；MFA 界面「停止」按钮未实机点过；预设「正式每日」（35 分钟级，耗时长）未实机跑；MFA 预设无法设定任务重复次数，「1 分钟试跑」里自动阅读默认仍是 2 次，需要手动改成 1（或接受 2 次耗时）；点击奖励入口后若页面加载慢，最坏要等 2～3 分钟才报错（`_wait_for_reward_page` 7 轮 × 15 秒等待的设计上限）；MFA 自身的告警（Mirror 酱资源更新检查失败、首次保存配置时的 IOException）确认不影响任务运行，未进一步处理。
**分支**：`claude/mfa-gui-20261006`
**回滚**：`git log --oneline -S "接入 MFAAvalonia 作为日常 GUI" -- CHANGELOG.md` 定位到合并提交后 `git revert -m 1 <hash>`。

---

## 2026-10-04 · 修复浏览广告误点领取及新版等级页返回漏识别

**触发**：最新完整串行 `runtime/records/daily_flows/daily_20261005_012306_a21ca029.json`：阅读2×33分钟、游戏25分钟、听书35分钟成功；每日广告97秒后报 `ad_exit_unconfirmed`，等级广告118秒失败。原始 Maa 日志已保存到 `runtime/records/ad_level_failure_20261004_214027.log`，真实 OCR 回放逐帧标注来源，省略无关昵称字段。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| 每日广告 `AdTaskAdapter.advance` | 浏览广告退出后又回到加速弹窗，最终关闭未确认 | 21:01:11点击“去领取奖励”(358,776)，同帧也有“坚持退出”；前者返回第三方体验加速入口，并非关闭。后续左上固定点击和BACK无效 | 优先明确的“坚持退出”；浏览体验页不把“去领取奖励”当出口；新帧定位顶部“去体验5秒可立即领奖｜跳过”，复用退出后的页面确认 |
| 等级广告普通运行时覆盖 | 21:39:39已返回等级页，仍等待20次至失败 | 新版顶部只有“当前等级/等级福利”，返回规则漏识别；`AdConfirmSkipBrowse` 的返回候选还排在DirectHit等待之后 | 返回确认补新版文字，已知返回页先于无条件等待，再按原广告来源anchor进入赠币或积分核对 |
| 积分完成核对 | 回到顶部找不到下面的积分任务行 | 原核对滑动向顶部，而任务行在下方；跨帧核对缺验证码候选 | 向下寻找积分行，保留5次预算和任务行“今日已完成”判据；三个返回/核对节点前置现有验证码候选，不改守卫、求解器构造或启用逻辑 |

**改动文件**：`qqreader/tasks/ad.py`、`scripts/run_task.py` 普通等级覆盖、`tests/test_ad_level_latest_failures.py`、`tests/fixtures/ad_level_latest_20261004.json`、`tests/test_level_ad_runtime_overrides.py`、本日志。

**验证**：
- 原始OCR：浏览挽留弹窗20176行，加速弹窗21088行，新版等级顶部25871行。回归先复现“去领取奖励”误点、顶部跳过漏定位、返回页被等待截走、赠币来源顶部返回漏识别；独立复核又发现核对跨帧验证码缺口，3项真实顶部背景+验证码叠层回放先失败，再修复为阻塞。
- `py -3.10 -m pytest -q tests/test_ad_level_latest_failures.py tests/test_ad_failures_20261004.py tests/test_level_ad_runtime_overrides.py tests/test_level_ad_stage_route.py tests/test_qqr54_level_ad_retention.py tests/test_qqr31_live_ad.py`：58 passed。新增11项。独立只读复核最终无残留重要问题；覆盖幂等，来源anchor及业务完成候选保留。
- 全量 `py -3.10 -m pytest -q --junitxml=runtime/records/ad_level_latest_fix_20261004.xml`：542项，535 passed、4 failed、3 skipped。失败仍为既有 `test_each_ad_round_has_its_own_initial_wait`、`test_live_exit_attempt_does_not_restart_eight_swipe_cycle`、`test_detect_slide_accepts_real_captcha_fixture`、`test_ad_play_waits_40_seconds_before_handling_buttons`；Tk后台线程warning仍存在，GUI测试的skip随本机初始化状态变化。`git diff --check`通过。
- 正式 GUI 广告首轮 `daily_20261005_035355_f5e50c75`：应用全黑且OCR为空，随后出现“QQ阅读没有响应”，未进入广告。按短时观察停止，CANCELLED，61.496秒；这次不能证明广告修复有效。停止后应用自行恢复书架，未重启模拟器或改配置。
- 正式 GUI 等级广告 `daily_20261005_035540_a9448ad3`：自动进入等级→播放积分广告→奖励已发放→关闭返回→积分行“今日已完成”，SUCCEEDED（exit0，39.772秒）。完成OCR在 `runtime/records/latest_level_validation_20261004_215540.log:3346`，按钮框(569,578,102,24)；MuMu界面确认同一“看小视频，+5积分”行完成。该次返回为旧版任务区域，新增顶部返回分支由真实失败帧回放覆盖。
- 应用恢复后通过 MuMu 界面返回书架，再正式 GUI 复验广告 `daily_20261005_035751_d5df973f`：自动进入奖励页→播放广告→关闭→返回奖励页，广告卡计数为1/12；其间出现验证码，由既有流程处理，本轮未修改或人工操作验证码。按短测停止，CANCELLED，总73.061秒，实际超过一分钟要求，未继续跑满12次。Maa证据保存到 `runtime/records/latest_ad_validation_20261004_215751.log`。该次广告是上滑浏览类型，未实机触发本次浏览退出弹窗优先级修复，该分支有原失败OCR回放与既有handoff转场证据。
- GUI设置与 `runtime/records/gui_tasks_before_latest_ad_fix_20261004.json` 语义一致，未改任务顺序、原时长、超时或本地验证码设置。

**未覆盖 / 遗留**：每日广告12/12、三天无人值守未作本次短时验收；禁止购买、充值、登录授权等操作仍保持。浏览加速广告坚持退出会放弃该条奖励，正常流程需继续下一条；不能将返回页当作收益。无响应现场未自然复现到诱因，未改网络或持久配置。已成功的阅读、游戏、听书未重复运行。原有验证码截图删除和快捷方式保留。
**分支**：`codex/reading-game-log-fix-20261004`
**回滚**：上一提交 `c550e59`；单独revert本次提交，不覆盖运行记录及用户设置。

---

## 2026-10-04 · 修复等级广告返回路由并隔离旧任务运行资源

**触发**：用户要求继续根据错误修正。上一轮正式 GUI 日志 `runtime/records/level_verification_20261004_182333.log` 中，积分广告返回后在18:24:28进入 `LevelAfterCoinAd`，绕过积分广告有界重试；GUI强制停止子进程还会跳过旧任务包装器的 `finally`，将临时覆盖留在共享资源中。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| 等级广告返回 | 积分广告误走赠币分支，重新进入原积分入口 | `AdReturnStable.next` 用固定候选代替已有 `LevelAfterAd` anchor；赠币与积分返回页特征相似，候选顺序无法区分来源 | 普通等级广告覆盖恢复框架支持的 anchor 引用；入口设置的来源决定返回分支，验证码候选仍优先；未绑定来源时不猜测阶段 |
| 旧任务运行资源 | GUI强制停止后共享 pipeline 留有运行时覆盖 | 覆盖与选书模板直接写入 `dev/resource`，恢复依赖会被强停跳过的 `finally` | 每次运行复制完整资源包到独立 `runtime/legacy_resources/legacy-*/resource`，覆盖、选书模板及子进程资源参数均使用独立副本；正常结束清理，强停残留副本不影响后续任务 |

**改动文件**：`scripts/run_task.py`、`tests/test_qqr54_level_ad_retention.py`、`tests/test_level_ad_stage_route.py`、`tests/test_legacy_resource_isolation.py`、`tests/fixtures/level_stage_return_20261004.json`、本日志。未修改验证码求解器、守卫构造或启用配置。

**验证**：
- 积分返回真实 OCR fixture 来源为上一轮日志6359行（18:24:27.555）；检查原积分入口、第二次入口、赠币来源、无来源和验证码优先分支。修复前4项失败、1项通过，修复后5项通过。现有本地 pipeline schema 的 NodeAttr 支持 `name` 与 `anchor: true` 引用。
- 资源隔离3项修复前均失败；修复后检查子进程启动时共享资源字节不变、选书模板不覆盖源文件，以及真实 Windows 父子进程经 `taskkill /T /F` 强停后源文件不变。强停测试仅终止测试自己创建的进程。
- `py -3.10 -m pytest -q tests/test_legacy_resource_isolation.py tests/test_issue13_legacy_timeout.py tests/test_book_device_selection.py`：43 passed。`py -3.10 -m pytest -q tests/test_level_ad_stage_route.py tests/test_ad_failures_20261004.py tests/test_level_ad_runtime_overrides.py tests/test_qqr54_level_ad_retention.py tests/test_legacy_resource_isolation.py`：47 passed。独立只读代码复核未发现新增重要问题。
- 全量 `py -3.10 -m pytest -q --junitxml=runtime/records/legacy_route_fix_20261004.xml`：531项，525 passed、4 failed、2 skipped；4项与本轮改动前一致：`test_ad_round_regressions::test_each_ad_round_has_its_own_initial_wait`、`test_ad_round_regressions::test_live_exit_attempt_does_not_restart_eight_swipe_cycle`、`test_issue15_reward_nav::test_detect_slide_accepts_real_captcha_fixture`、`test_qqr27_ad_flow::test_ad_play_waits_40_seconds_before_handling_buttons`。既有 Tk 后台线程 warning 仍存在。
- 正式 GUI 短测 `daily_20261005_011503_22432a7a`（业务日10-04）：实际使用 `runtime/legacy_resources/legacy-dvuu81xa/resource` 成功加载资源并执行。19:15:24进入积分广告；19:15:40返回 `LevelAfterPointsAd`，积分再次入口执行2次后在19:16:18转入 `LevelVerifyPointsScroll`，不再误走赠币阶段。节点证据保存在 `runtime/records/level_route_verification_20261004_191503.log`。
- 从 GUI 停止后记录为 CANCELLED，开始17:15:03.035487 UTC、结束17:16:30.348311 UTC，总87.313秒；实际超过用户要求的一分钟，按实际时长记录。共享 pipeline 运行前、运行中、停止后 SHA-256 均为 `D0092F69CA076AEF9954EB441902936F5FA93716FC0F06F57874F5DC20AD24F8`，无需人工恢复。GUI任务设置与本轮备份 `runtime/records/gui_tasks_before_route_fix_20261004.json` 语义一致，保留用户调整后的听书顺序。

**未覆盖 / 遗留**：此次实机积分广告为浏览类，现有策略仍走跳过/放弃，任务按钮未完成，没有积分到账或整体SUCCESS证据；浏览类广告完成策略与最终领奖尚需后续修正。未重跑已成功的阅读、游戏、听书，未验证三天无人值守。强制终止可能留下独立资源目录，占用磁盘但不污染共享资源；未新增自动清理策略。原有验证码截图删除及快捷方式保留，不纳入提交。
**分支**：`codex/reading-game-log-fix-20261004`
**回滚**：上一提交 `0e8c5bf`；单独 revert 本次提交，不覆盖运行记录或用户设置。

---

## 2026-10-04 · 修复广告已领取出口与等级广告盲滑、入口遮罩

**触发**：用户要求继续根据今日日志修正问题，并仅短时实机验证。最新完整串行记录 `runtime/records/daily_flows/daily_20261004_130234_ea52341f.json` 中阅读33分钟、游戏25分钟、听书35分钟均 SUCCEEDED；每日广告在 `DailyAdFlow_20261004_081823_717207.json` 报 `ad_exit_unconfirmed`，等级广告最终空滑240次失败。因此本次只复查剩余广告问题，不重跑已成功任务。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| `qqreader/tasks/ad.py` | 广告已显示奖励领取，关闭20秒仍不能返回 | 真实截图 `runtime/screenshots/20261004/DailyAdFlow_20261004_081233_424163_037_PAGE_AD_PLAYING.png` 没有 X，出口为右上“奖励已领取｜跳过”；旧识别没有该出口，回退点左上 | 新截图 OCR 确认右上已领取/已发放的跳过出口再点击；不把中部“返回继续体验”当退出按钮 |
| 等级广告运行时覆盖 | 仅状态栏的加载帧开始滑动，之后落在“我的”仍滑240次 | `AdScrollDownRepeat` 为无条件 DirectHit；没有未知页等待和“我的”重入 | 滑动前要求广告特征；未知页仅等待重拍，最多20次；确认“我的”后按实际等级文字重入并确认等级页，最多3次 |
| 等级入口 | 实机33秒后仍在书架；下一次进入“我的”却31秒后失败 | 升级提示挡住底部“我的”；双倍月票活动遮罩挡住等级图标；原候选链没有普通遮罩处理及我的入口重试 | 先确认升级文案，再找右下“取消”；我的入口未转场最多重试2次；先确认活动标题，再仅在中下方限定ROI找 X，排除基因图标 |

**改动文件**：`qqreader/tasks/ad.py`、`scripts/run_task.py` 的普通等级广告运行时覆盖、`tests/test_ad_failures_20261004.py`、`tests/fixtures/ad_failures_20261004.json`、`tests/test_level_ad_runtime_overrides.py`、本日志。未修改验证码求解器、守卫构造、启用参数或本地配置。

**验证**：
- 使用原始 Maa 日志 OCR 框逐帧回放；来源在 fixture 内逐帧标注。10-04早间原始日志 `runtime/logs/maafw.bak.2026.10.04-08.31.24.108.log`：已领取跳过21306行、等级入口22837行、空白加载22867行、落回我的24377行。新入口失败日志另保存在 `runtime/records/level_entry_failure_20261004_181534.log`；活动遮罩失败保存在 `runtime/records/level_promo_failure_20261004_181915.log`。
- 回归先失败再修复：已领取出口实际框中心(622,27)、未知页不滑、我的重入、20次等待边界、覆盖幂等性、升级/活动遮罩关闭与点击未转场重试。独立只读复核发现新增恢复入口的验证码优先级遗漏，补上现有 `LEVEL_CAPTCHA_NODES`，真实背景与验证码提示组合回放确认不点击背景或弹窗 X；最终审查无新增重要问题，原广告来源 anchor 保留。
- `py -3.10 -m pytest -q tests/test_ad_failures_20261004.py tests/test_level_ad_runtime_overrides.py tests/test_qqr54_level_ad_retention.py`：39 passed。
- 正式 GUI 每日广告 `daily_20261005_001320_ec572e08`（业务日仍为10-04）：超时临时设1分钟，自动进入并播放广告，点击本次实际左上关闭框(53,112)，返回奖励页出现验证码；现有流程处理并确认验证码消失，随后 TIMEOUT（exit11；任务62.343秒，GUI总耗时1分06秒）。任务记录 `runtime/records/DailyAdFlow_20261004_181425_901811.json`。未触发本次新增右上已领取跳过出口，未达到12/12。
- 等级广告首轮 `daily_20261005_001534_a3c82e25`：33秒 FAILED（exit2），复现升级遮罩；补修后第二轮 `daily_20261005_001915_d55e4b77`：31秒 FAILED（exit2），复现月票遮罩。现场通过 MuMu GUI 关闭已确认的普通活动弹窗，截图确认等级图标可见；自动关闭分支由原始OCR回放验证。
- 最终正式 GUI `daily_20261005_002333_b231c770`：自动确认我的页→点击等级→确认等级页→找到并点击赠币广告→实际播放广告。按短时观察要求从 GUI 停止，终态 CANCELLED（总1分13秒，含停止响应）；未声称奖励到账。运行节点与输入证据保留在 `runtime/records/level_verification_20261004_182333.log`。
- 强制停止旧任务后 `finally` 未恢复临时资源；先备份到 `runtime/records/level_runtime_before_restore_20261004.json`，只逆转本次运行覆盖字段，保留阅读/听书等已有本机资源差异；重新应用覆盖后与停止时快照完全一致，恢复清单在 `runtime/records/level_runtime_restore_20261004.json`。未提交生成资源。曾在旧任务运行中并行全量测试，3项原始pipeline检查受到临时覆盖影响；该次结果不作最终验收。
- 停止、恢复后重新执行 `py -3.10 -m pytest -q --junitxml=runtime/records/ad_fixes_20261004.xml`：523项，518 passed、4 failed、1 skipped。4项与改动前一致：`test_ad_round_regressions::test_each_ad_round_has_its_own_initial_wait`、`test_ad_round_regressions::test_live_exit_attempt_does_not_restart_eight_swipe_cycle`、`test_issue15_reward_nav::test_detect_slide_accepts_real_captcha_fixture`、`test_qqr27_ad_flow::test_ad_play_waits_40_seconds_before_handling_buttons`。原 GUI Tk 后台线程 warning 仍存在。`git diff --check` 通过。

**未覆盖 / 遗留**：每日广告12/12、等级赠币/积分“今日已完成”及到账未完成本次短时验收；新增右上出口、升级及活动自动关闭、未知页20次恢复预算均未在最终实机复验触发。强制终止旧包装器后临时资源不会自动恢复，已在本次现场恢复，未扩大到停止机制重构。GUI参数与 `runtime/records/gui_tasks_before_ad_fixes_20261004.json` 语义一致，广告45分钟、等级30分钟已保留。既有验证码fixture删除和快捷方式均保留，不纳入提交。
**分支**：`codex/reading-game-log-fix-20261004`
**回滚**：上一提交 `10186de`；本条代码修改单独 revert 本次提交即可，不恢复或覆盖运行记录。

---

## 2026-10-04 · 一分钟实机复验：避免阅读返回后在受保护正文调用 OCR

**触发**：用户要求修复后仅用一分钟实机验证。正式 GUI `daily_20261004_121807_797ddd8f` 在 06:19:28 完成一分钟正文计时，但第一次 BACK 只取消选中文字，正文仍禁止截图；随后检查退出弹窗立即调用 Maa OCR，陷入截屏重连。06:21:25 从 GUI 停止后子进程已结束，GUI 仍显示“正在停止”，该记录未正常写回终态，随后关闭并从正式启动脚本重开 GUI，保留原记录。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| `scripts/auto_read_30min.py::return_to_capturable` | 计满一分钟后无法返回，持续截屏重连 | BACK 不一定退出正文，可能只取消选文或停止自动滚动；原逻辑每次 BACK 后立刻 Maa OCR | 若 ADB 截图不可用且前台仍明确是正文，跳过 OCR，继续原有有界返回；非正文保留 Maa 检查及验证码阻塞，不能只凭 ADB 截图失败跳过验证码 |

**改动文件**：`scripts/auto_read_30min.py`、`tests/test_reading_interruptions.py`、本日志。
**验证**：
- 回归先复现受保护正文进入 OCR 的失败，再验证两次 BACK 后才 OCR；另覆盖 ADB 截图失败但前台非正文、Maa 能识别验证码时立即阻塞，不额外发送 BACK。独立只读审查发现并复核了后一个边界，最终无新增问题。
- `py -3.10 -m pytest -q tests/test_reading_interruptions.py`：11 passed。全量 `py -3.10 -m pytest -q --junitxml=runtime/records/one_minute_fix_20261004.xml`：498 项，492 passed、4 failed、2 skipped。4 项仍为上一条记录列出的基线失败，未新增失败；原 GUI Tk 后台线程 warning 仍存在。
- 正式 GUI 第二次阅读尝试 `daily_20261004_122657_a1cdc8ba`：书架未恢复就绪，23 秒后 FAILED（exit 2），现场已在 MuMu 桌面，未开始阅读。通过 GUI“启动QQ阅读” `daily_20261004_122742_7c800ba4` 重新打开后，实机确认完整书架，未伪造前一次成功。
- 最终阅读复验 `daily_20261004_122842_f736970b`：06:28:53 自动打开指定书、06:29:59 计满 1/1 分钟、06:30:04 自动返回两次到可截图页面，正文运行及返回阶段通过。随后领奖页显示今日14分钟、10分钟档已领取、30分钟档未到；领奖检查 exit 2，因此整项仍 FAILED（总耗时1分42秒）。未追加阅读时长或声称新奖励到账。
- 正式 GUI 游戏一分钟 `daily_20261004_123116_a62e9841`：自动进入在线时长任务、打开游戏、开始计时、自动退出并返回 GAME_ENTRY；SUCCEEDED（exit 0，总耗时2分11秒，含加载及返回）。任务记录 `runtime/records/DailyGameFlow_20261004_063322_949686.json` 与关键截图均保留。只验证短时运行闭环，未验证20分钟奖励到账。

**未覆盖 / 遗留**：未跑满阅读33分钟、游戏25分钟或三天无人值守；未实机触发验证码。第一次停止后 GUI 终态未写回及非就绪书架现场未在本次小修中全面处理。验证后通过 GUI 恢复阅读33分钟、游戏25分钟，其他设置与 `runtime/records/gui_tasks_before_one_minute_20261004.json` 保持一致。
**分支**：`codex/reading-game-log-fix-20261004`
**回滚**：上一轮修复提交 `bade9e4`；本次提交可用 `git log --oneline -S "一分钟实机复验：避免阅读返回后在受保护正文调用 OCR" -- CHANGELOG.md` 定位后单独 revert。

---

## 2026-10-04 · 修复阅读中断、领奖导航及游戏误点入口

**触发**：用户要求依据今日日志修正自动阅读失败、每日游戏无法打开。正式 GUI 记录 `runtime/records/daily_flows/daily_20261004_110610_70bbe0cb.json`：阅读 33 分钟在 85 秒后 FAILED（exit 2），随后游戏被用户停止；`runtime/logs/auto_read.log` 05:07:35 报“第 1/3 段第 1 分钟时已离开正文页”。`runtime/logs/maafw.bak.2026.10.04-05.16.23.464.log` 05:09:49、05:10:21 实际点击充值行“去玩游戏”，进入空白 H5。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| `scripts/auto_read_30min.py` 正文确认与计时 | 正文中断后直接退出；每分钟确认前还会继续翻页 | 在完整窗口列表中查 `ReaderPageActivity`，后台窗口也能被误放行；三次翻页后才确认焦点，没有确认安全页面后重新进入的分支 | 只看前台焦点，自动阅读按钮操作及每次翻页前后确认；中断时保存焦点、OCR、截图；确认书架/书城/奖励页/弹窗后最多两次重新进入白名单书，UNKNOWN 重拍不点击；被中断的分钟重新计满 |
| 同上恢复/选书与失败清理 | 复查中新出现验证码可能被普通导航失败捕获，继续按返回 | `ReadingBlockedByCaptcha` 是 `RuntimeError` 子类，原普通 catch 会吞掉阻塞异常 | 每次 OCR 新帧先检测验证码；选书、回书架显式传播验证码异常；失败清理遇验证码也返回 exit 10，保留现场。未修改滑块求解器或启用逻辑 |
| `qqreader/tasks/reading_reward.py::_open_reward_page` / `qqreader/reward/nav.py::goto_reward_page` | 阅读十分钟后领奖无法进入奖励页，返回后困在退出框；正确点击后加载帧仍被判失败 | 独立领奖导航先点“再读9分钟领20赠币”说明文字 (165,205)，没有点真正按钮 (597,180)；盲 BACK 不处理退出确认框；统一导航见 H5 过渡帧立刻返回 False | 领奖复用统一导航、优先时长卡按钮；“确定退出QQ阅读”先点取消再重拍；未知/加载帧在原12步预算内等待重拍，期间无输入，仍未确认才退出 |
| `qqreader/tasks/game.py::_open_game_row` | 在线时长任务和充值任务都有“去玩游戏”，实际点了充值入口 | 全屏 OCR 最佳匹配选中下方同名按钮，没有绑定任务标题 | 新截图内只点“玩游戏领赠币”标题同一行按钮；缺失目标只在确认奖励页时受控滚动，不用同名按钮或固定点击兜底；点击后等待下一帧确认，不提前开始计时 |
| `scripts/run_task.py::_build_runtime` 与游戏恢复 | 第一轮复验遇网页断连、QQ 阅读无响应，恢复到 MuMu 桌面后反复按返回 | 运行观察未接已有 `DeviceProbe`，前台包名一直为 None；桌面“游戏中心”图标被当游戏列表 | 注入现有 ADB 只读前台探测；明确 `com.mumu.launcher` 时最多三次重新打开 QQ 阅读，保留游戏计时、已退出及待领奖状态 |

**改动文件**：上表五个代码文件、`tests/test_daily_entry_20261004.py`、`tests/test_reading_interruptions.py`、`tests/fixtures/daily_entry_20261004.json`、本日志。

**验证**：
- 新增真实 OCR 回放：两种奖励页布局都点击在线时长任务，充值行单独存在时不点；新帧有验证码不点；桌面恢复保留游戏退出状态；实际运行组合注入前台包名。阅读回放覆盖后台正文窗口、书架中断重新进入、UNKNOWN 不盲点、恢复/选书中新验证码不返回，另检查三类失败清理保留验证码 exit 10。关键失败先在修复前复现（选书验证码回放实际记录一次错误 BACK）。
- 相关检查 `py -3.10 -m pytest -q tests/test_reading_interruptions.py tests/test_daily_entry_20261004.py tests/test_daily_popups.py tests/test_qqr55_reading_shelf.py tests/test_autoread_book_guard.py tests/test_book_device_selection.py tests/test_reading_reward_claim.py`：108 passed。
- 全量 `py -3.10 -m pytest -q --junitxml=runtime/records/final_fix_20261004.xml`：496 项，490 passed、4 failed、2 skipped；基线 478 项：472 passed、4 failed、2 skipped。新增18项均通过。4 项原有失败是 `test_each_ad_round_has_its_own_initial_wait`、`test_live_exit_attempt_does_not_restart_eight_swipe_cycle`、`test_detect_slide_accepts_real_captcha_fixture`、`test_ad_play_waits_40_seconds_before_handling_buttons`；前两类涉及广告等待/退出，fixture 涉及本次开始前已删除的截图，均未纳入修复。跳过项为本机 Tk 初始化不稳定的一项 GUI 测试及缺真实截图的验证码测试，GUI 测试后台线程 Tk warning 仍存在。
- 正式 GUI 游戏 1 分钟首轮 `daily_20261004_113523_ea2230ea`：正确进入游戏并计时；返回时网页 `ERR_CONNECTION_CLOSED`、QQ 阅读无响应，退到桌面空转，随后从 GUI 停止，CANCELLED（不能记成功）。补前台探测后复验 `daily_20261004_114447_b7c38036`：进入正确游戏入口、启动并计时、退出返回奖励页，SUCCEEDED（exit 0，2 分 42 秒），任务证据 `runtime/records/DailyGameFlow_20261004_054724_305415.json`。奖励页显示“再玩18分钟即可领取”，因此这里只验证短时游戏闭环，**没有宣称20分钟档奖励到账**。
- 正式 GUI 阅读 10 分钟 `daily_20261004_114942_62515434`：05:50 主动通过模拟器界面返回书架进行受控中断；05:50:56 留书架现场，05:50:59 确认原书、05:51:00 重新进入正文；06:01:22 计满10分钟、06:01:24 返回书架。该次整项仍 FAILED（exit 2），因暴露原有领奖入口问题。修复入口优先级后 `daily_20261004_120406_5f0f3a23` 从退出确认框重试仍失败（exit 3）；取消退出框修复后 `daily_20261004_120704_ce371ab9` 遇持续黑屏，exit 3；正式界面关闭 QQ 标签、再用 GUI 启动 QQ 阅读恢复后，书架显示时长735→745分钟，确认本轮阅读被应用记录。`daily_20261004_121006_3c857576` 再暴露 H5 过渡帧立即失败（exit 3），已加入等待重拍。
- 最终 GUI 领奖补跑 `daily_20261004_121145_14a100b6`：SUCCEEDED（exit 0，17秒）；结果“赠币10→30”，10分钟档变为“已领取”，30分钟档仍未达到。证据 `runtime/screenshots/reading_reward_claim_before_20261004_061153.png`、`reading_reward_claim_after_20261004_061202.png`。此次十分钟阅读、中断恢复与20赠币到账分别有实机证据，**没有把前面失败记录改写成整项成功**。

**未覆盖 / 遗留**：
- 原始 05:07 阅读为何离开正文未自然重现，原日志缺少当时焦点与现场截图；此次修复的是可确认的前台判据和缺失恢复分支，实机中断为主动注入，不能写成重现原始诱因。
- 未实机跑满阅读 33 分钟、游戏 25 分钟，未覆盖阅读跨段返回和三天无人值守；UNKNOWN/验证码及桌面重入分支主要由真实帧回放和单元测试覆盖。原有选书等待正文失败后的固定“查看原文”备用点击没有全面改造。
- 第一轮实机网络断连与 QQ 阅读无响应属于现场故障，未修改代理或网络持久配置。原有广告测试差异、截图删除及快捷方式保留。
- 领奖整段尚未实机遇验证码；统一入口会停止点击，但领奖上层仍可能记普通导航失败，验证码专用 outcome 尚非此次完整覆盖。最后领奖补跑前有通过正式界面的人工应用重开，未验证黑屏无人干预恢复。
- 验证结束后通过 GUI 恢复阅读 33 分钟、游戏 25 分钟；`runtime/gui_tasks.json` 与测试前备份的 JSON 内容完全一致，勾选项和其他设置均已恢复。

**分支**：`codex/reading-game-log-fix-20261004`
**回滚**：`git log --oneline -S "修复阅读中断、领奖导航及游戏误点入口" -- CHANGELOG.md` 定位本次提交后 `git revert <hash>`。GUI 测试前配置备份：`runtime/records/gui_tasks_before_20261004_fix.json`。

---

## 2026-10-02 · 修复滑块验证码求解器写死配置路径导致的崩溃，恢复自动求解后继续任务

**触发**：用户反馈「遇到滑动验证码无法正常运行」，要求调用 GUI 模拟人工点击实机复现。`runtime/records/DailyAdFlow_20261001_173332_121299.json` 在 `captcha.detected` 之后立刻 `未预期异常: ConfigError: 配置文件不存在: configs\qqreader.local.json`，任务被判 FAILED（exit 2），滑块一次都没滑出去；`DailyAdFlow_20261001_192252_745520.json`、`DailyAdFlow_20261002_050425_790460.json` 则记为「未配置自动求解器，等待人工处理验证码」（那两次跑的是 `agent/T-008` worktree 的代码，其 `--captcha-mode manual` 默认值强制人工守卫，不在本次改动范围）。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| `qqreader/captcha/slide.py::_sendevent_track` | 识别到验证码后任务以「未预期异常 ConfigError」失败，验证码一次都没滑 | 函数第一行 `load_config("configs/qqreader.local.json")` 写死**相对当前工作目录**的路径；cwd 不是仓库根目录（worktree / 快捷方式 / 打包 exe / 在别的目录跑 CLI）时抛 ConfigError，异常一路冒到 runner 的通用异常分支 | 新增 `_resolve_adb_endpoint()`：显式注入 → 运行时 Maa 客户端 `config.adb_path/adb_address` → `_REPO_ROOT/configs/qqreader.local.json`（按文件位置解析）；sendevent 注入拆到 `_inject_sendevent_track()` |
| 同上 | 取不到 adb 端点 / adb 可执行文件不存在 / sendevent 写入失败时整个任务崩成 FAILED | 没有降级路径：`getevent` 探测与 `send()` 失败都直接抛异常 | 先降级为 `device.swipe()`；再失败只抛 `SlideInputUnavailable`，由 `solve()` 转成 `solved=False`（→ `BLOCKED_BY_CAPTCHA` 等待人工），并把降级原因写进失败详情 |

**改动文件**：`qqreader/captcha/slide.py`、`tests/test_qqr34_slide_captcha_runtime_adb.py`、本日志。
**验证**：
- 修复前确认失败：把 cwd 切到 `runtime/_cwd_probe` 后，HEAD 版 `_sendevent_track` 抛 `ConfigError: 配置文件不存在: configs\qqreader.local.json`（与 10-01 17:33 实机同一报错）；同一脚本里修复后的版本按仓库根目录解析出 `adb.exe` + `127.0.0.1:16384`，不再依赖 cwd。
- 新增 8 项回归测试 `tests/test_qqr34_slide_captcha_runtime_adb.py`：运行时端点解析、cwd 不在仓库根目录时不读相对路径、无端点 / 无 adb / 设备 swipe 也失败三种降级路径，以及用 10-01、10-02 真实验证码截图跑完整求解循环（`solved=True`）。
- GUI 实机（`启动QQReaderGUI.cmd` 启动；用 Win32 子窗口矩形匹配定位控件后模拟点击「全不选」→ 只勾「每日广告完整流程」→「直接运行已选」）：串行记录 `daily_20261002_141758_d366cb4e`，单步 `01-DailyAdFlow-1` → `SUCCEEDED`，exit 0，10 分 45 秒；任务记录 `DailyAdFlow_20261002_082834_335033.json` 命中 `success_condition`（`OCR 包含 "12/12"`）。
- 验证码分支实测：08:19:32 `CAPTCHA_DETECTED`（`runtime/screenshots/20261002/DailyAdFlow_20261002_081932_349657_009_CAPTCHA_DETECTED.png`，检测到轨道 (75,806,567,26)、滑块中心 (168,818)、缺口 x=472、距离 304px）→ 求解器滑了 4 轮（304px 连续三次被拒后重新随机化，第 4 轮 409px 通过）→ 08:20:15 `CAPTCHA_CLEARED`（同目录 `..._010_CAPTCHA_CLEARED.png`，该帧已无滑块轨道）→ 记录 `captcha.handled resolution=SOLVED attempts=1` 与 `captcha.verified_gone 已确认验证码消失，恢复原任务` → 广告流程继续跑到 12/12。对照 10-01 19:21 与 10-02 05:02 的同一位置，前两次都以 `BLOCKED_BY_CAPTCHA` 结束。
- 全量 `py -3.10 -m pytest -q`：478 项，472 passed、4 failed、2 skipped；4 项失败与改动前完全一致（广告 40/35 秒等待差异两项、直播退出一项、被删除的 `runtime/screenshots/ad_watch/captcha_now.png` fixture 一项），不是本次引入。`pytest -q` 末尾的汇总行本机被截断，数量取自同一次运行的 `--junitxml` 结果（tests=478 / failures=4 / skipped=2）。

**未覆盖 / 遗留**：
- 实机 GUI 运行的 cwd 就是仓库根目录，这条路径原本也能读到配置。被修的是「cwd 不是仓库根目录」的启动方式（worktree / 打包 exe / 快捷方式 / 在别的目录跑 CLI）；该分支只由单元测试和修复前复现脚本覆盖，**没有实机复现**。
- `agent/T-008` worktree 里 `scripts/run_task.py` 的 `--captcha-mode manual` 默认值，以及 GUI `build_run_task_command` 强制追加该参数的问题原样保留，未纳入本次改动（用户要求只修当前检出）。那次改动正是 10-01 19:21 / 10-02 05:02 两次「未配置自动求解器」的来源。
- 实机未触发「取不到 adb 端点」与「sendevent 写入失败」两条降级分支，只由单元测试覆盖。
- 为复现验证码，实机跑掉了当天广告 12/12（成功）；GUI 勾选状态已恢复为操作前的 5 项，验证用的 GUI 实例已关闭。

**分支**：`dsh/qqr-34-slide-captcha-cwd-20261002`
**回滚**：`git log --oneline -S "修复滑块验证码求解器写死配置路径导致的崩溃" -- CHANGELOG.md` 定位本次提交，随后 `git revert <hash>`。

---

## 2026-09-30 · 等待书架列表加载后确认自动阅读书目，避免启动即白名单拒绝

**触发**：用户要求修正无法自动阅读。GUI 每日运行 `daily_20260930_103417_205adb77` 的阅读任务在 28 秒后 exit 3；`runtime/logs/auto_read.log` 04:34:44 报“书架上没有白名单书目”，但现场截图已出现《宇智波：从扉间人柱力开始》。Maa 日志 04:34:41.645 仅识别到书架导航和时长卡，04:34:56.076 才识别到完整书籍列表。

| 任务/模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| 自动阅读选书确认 | 页面已是书架，列表尚未加载时直接拒绝目标书 | 首帧没有书名就抛出 `BookNotAllowed`，未等待列表加载 | 最多 6 次重新截图确认；在书架未找到指定书名时等待 3 秒再重拍，预算耗尽才拒绝，不点击其他书 |
| 选书复查中的验证码 | 延迟复查可能遇到验证码 | 普通页面恢复不能在验证码上执行 | 检查验证码文案，保存证据并返回 `BLOCKED_BY_CAPTCHA`（exit 10），不执行失败返回清理 |

**改动文件**：`scripts/auto_read_30min.py`、`tests/test_qqr55_reading_shelf.py`、`tests/fixtures/autoread_loading_frames.json`、本日志。
**验证**：
- 新增 5 项回归测试均先在修复前确认失败；使用 09-30 真实 Maa OCR 加载帧、已加载帧，以及已有真实验证码帧。
- `py -3.10 -m pytest -q tests/test_autoread_book_guard.py tests/test_qqr55_reading_shelf.py tests/test_daily_popups.py tests/test_book_device_selection.py`：84 passed。
- 全量 `py -3.10 -m pytest -q`：464 passed、4 failed、2 skipped、1 warning；4 项失败与修改前一致（广告 40/35 秒等待差异两项、直播退出一项、原有删除的验证码截图 fixture 一项）。`git diff --check` 通过。
- 正式 GUI 点击“单独运行此任务”，运行 `daily_20260930_120351_9f58b7b1`：1 次 × 1 分钟，自动选中《宇智波：从扉间人柱力开始》，观察正文持续向下翻页，日志确认 1/1 分钟、返回可截图页面；随后确认阅读奖励已领取，exit 0，GUI 显示成功（1 分 34 秒）。测试后 GUI 阅读设置恢复为 1 次 × 33 分钟，其他每日任务未重复执行。

**未覆盖 / 遗留**：本次实机列表及时加载，延迟加载和验证码分支由真实帧回放覆盖；未实机跑满 33 分钟或验证跨段返回、服务端新增阅读时长与新奖励到账；全量测试的 4 项原有失败未修。原有 `qqreader/runner/runner.py` 修改、启动脚本及验证码截图删除均保留，未纳入本次提交。
**分支**：`codex/qqr-55-reading-ocr-20260930`
**回滚**：`git log --oneline -S "等待书架列表加载后确认自动阅读书目" -- CHANGELOG.md` 定位本次提交，随后 `git revert <hash>`。

---

## 2026-09-29 · 计划外弹窗统一优先找关闭按钮；修复奖励页被判书架、游戏退出后不领奖空转、阅读领奖漏读币值

**触发**：用户要求不要只处理固定弹窗——任何计划外弹窗都优先找关闭按钮（X 或「关闭」），并实机完整跑一轮（自动阅读 1 轮 × 10 分钟）。实机运行 `daily_20260929_111500_9cb3bb10` 和补跑 `daily_20260929_123918_ff2993fd` 又暴露三个原有缺陷。

| 模块 | 现象 / 原因 | 修改 |
| --- | --- | --- |
| `qqreader/page/blocking_popup.py`（重写） | 上一条按“签到成功”和“居中 X + 正上方按钮”两种固定版式识别，新活动换版式就会漏 | 通用规则：背景是计划内主页面（书架 / 奖励页 / 书城的独有文案）时，在屏幕中部（按钮中心 y 120～1150）先找关闭类文字（我知道了 / 知道了 / 关闭 / 以后再说 / 下次再说 / 暂不 / 暂不需要 / 残忍拒绝 / 不了 / 取消），再找单独的 X / × / ✕，多个取最靠中线的；弹窗盖满屏、只剩底部导航「书架 / 书城」tab 时只认居中（偏离中线 ≤40）的 X。排除页面自带 X：奖励页「邀请好友」一排头像占位（同行多个 X / + 或正下方「待邀请」）、听书时书架左下角悬浮播放器的 X（同屏「正在播放」，点了会停听书）。有验证码时一律不点。不点任何「立即参与 / 看视频额外领 / 立即领取」 |
| `scripts/run_task.py::_apply_external_popup_overrides` | 外部 App 覆盖节点原来只认「我知道了」 | 改名 `ExternalPopupDismiss`，OCR 整框匹配上述关闭类文字（去掉易与任务行文字混淆的「取消」「不了」），ROI `[0,120,720,1030]`；X 图形由交接检查处理（pipeline 节点排除不了邀请头像的 X） |
| `scripts/auto_read_30min.py::classify_page` | 实机 05:15：关掉签到弹窗后停在奖励页，奖励页的「今日再读7分钟领20赠币」含书架判据「再读」，被判成书架 → 白名单拒绝 exit 3 | 新增 `REWARD_PAGE_MARKERS`，先判「奖励页」，由回书架流程按返回键 |
| `qqreader/tasks/game.py`、`qqreader/contract/conditions.py::GameFlowCompleted`、`qqreader/reward/nav.py::find_row_button` | 实机 05:41～05:50：退出游戏后奖励页因「游戏任意充值领赠币 / 去玩游戏」行被识别成 `GAME_ENTRY`，成功条件只认 `REWARD_HOME`；领奖分支看到「今日已获赠币」50 → 70（其他任务的币）就判领取成功、不点游戏行的「立即领取」，每 10 秒空转一次直到 35 分钟超时 | 成功条件改为 `REWARD_HOME` 或 `GAME_ENTRY`；有设备客户端时退出游戏即置 `game_claim_pending`，回奖励页后重新截图，点「玩游戏领赠币」同一行（纵向 ≤45）的「立即领取」，该行不再有按钮才清除标记（最多点 3 次）；`GameFlowCompleted` 在标记未清除时不判成功 |

| `qqreader/tasks/reading_reward.py::claim_reading_rewards` | 补跑 06:50：只读 13 分钟，10 分钟档领到（赠币 194 → 214、按钮变「已领取」），30 分钟档按钮是灰的点不动；最后一帧 OCR 把「今日已获赠币」和数字拆成两个框，只看最后一帧就读不到币值 → 判“缺少币值证据” exit 2 | 点击过程中每帧都读币值，保留最后一次读到的值 |

**改动文件**：上表各文件；`tests/test_daily_popups.py`、`tests/fixtures/daily_popup_ocr_frames.json`（新增实机帧：另外两期活动弹窗、听书悬浮播放器、验证码帧、「我的」页、09-29 签到弹窗、签到后的奖励页、游戏退出后的奖励页、阅读领奖三帧）；本日志。
**验证**：
- 识别离线回放：`maafw*.log` 全部 11188 帧真实 OCR，只命中签到弹窗与三期不同活动弹窗（09-24 中秋找玉兔、09-27 现金红包〈盖满屏〉、09-28 秋日豪礼）；邀请头像、悬浮播放器、验证码、「我的」页、广告页、游戏页均不命中。
- 全量 `py -3.10 -m pytest`：456 passed、4 failed（master 原有已知失败，见 `claude/known-test-failures-20260929`）、1 skipped；新增用例全部用真实 OCR 帧，修复前对应用例均失败。
- 实机（worktree 代码；命令行按 GUI「直接运行已选」同一套 `build_serial_plan` / `build_run_task_command` / `build_handoff_command` / `apply_handoff` 串行，任务间隔 3 秒 + 交接检查；用户未授权桌面操作，未点 GUI）：

| 运行 | 任务 | 结果 |
| --- | --- | --- |
| `daily_20260929_111500_9cb3bb10` | 自动阅读 1×10 分钟 | 失败 exit 3：开跑即遇今日「签到成功」弹窗，第 1 次点「我知道了」时弹窗在动画中未关，重新截图后第 2 次关掉；随后奖励页被判书架（本次修复前代码） |
| 同上 | 游戏 25 分钟 | 失败 exit 11：挂机、退出正常，回奖励页后空转到 35 分钟超时（本次修复前代码） |
| 同上 | 广告 / 等级广告 / 听书 35 分钟 / 外部 App | 全部成功；每项前的交接检查均 READY |
| `daily_20260929_123918_ff2993fd`（补跑） | 自动阅读 1×10 分钟 | 起点停在奖励页（含被 OCR 成「X X」的邀请头像，未误点）→ 判「奖励页」按返回 1 次回书架 → 选中《宇智波》读满 10 分钟；领奖 exit 2（上表阅读领奖缺陷，已修复，仅由真实帧回放测试覆盖，未再实机补跑：今日已读 23 分钟，再读 10 分钟也到不了 30 分钟档，必然无可领） |
| 同上 | 游戏 25 分钟 | **成功**（27 分钟）：退出后点游戏行「立即领取」(592,611)，重新截图确认按钮消失后判成功 |

**未覆盖 / 遗留**：书架活动海报（X 图形）与「关闭」文字弹窗本次实机没有出现，只由历史真实帧回放和单元测试覆盖；阅读领奖修复未实机复跑；旧 pipeline 任务运行中途弹出的 X 图形弹窗只靠下一项前的交接检查关闭；奖励页里性质不明、偏离中线的 X 保守不点。实机运行使用 worktree 下复制的本机配置 `configs/qqreader.local.json` 与任务表 `runtime/gui_tasks.json`（均被 .gitignore 忽略，未入库）。
**分支**：`claude/daily-popup-dismiss-20260929`
**回滚**：`git log --oneline -S "计划外弹窗统一优先找关闭按钮" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-09-29 · 关闭书架每日运营弹窗与奖励页签到弹窗，避免后续任务全部卡住

**触发**：用户反馈每日第一次进奖励页时的签到弹窗没有及时关闭，自动阅读之后的任务全部卡住。运行 `daily_20260928_233026_1486afea`（`runtime/records/daily_flows/`）7 项全部失败；用 `runtime/logs/auto_read.log`、`gui_*.log`、`maafw.bak.2026.09.28-18.07/18.25.log`、`maafw.log` 的 OCR 逐帧还原。

| 时间（本机） | 现象 | 根因 |
| --- | --- | --- |
| 18:02（北京 00:02 跨天） | 自动阅读第 3 段回书架后 exit 3「书架上没有白名单书目」；第 2 次阅读同样 exit 3 | 书架弹出运营海报「双倍月票开启 / 秋日豪礼开抢 / 立即参与」，海报下方单独一个 X（OCR `X (342,930,33,32)`）。海报遮住书名（「宇智波」被读成「宇餐」），背景书架文案仍在，`classify_page` 判成书架 → 白名单拒绝。原活动弹窗只认写死的活动文案（「找兔子」等），不认识这一期 |
| 18:02～18:39 | 交接检查 5 次都判 READY；游戏在 HOME 连点 694 次「再读7分钟领20赠币」直到 35 分钟超时；广告 `ad_watch_entry_not_found`；等级广告失败 | `handoff.classify_frame` 同样把弹窗后的书架判成 SHELF；`reward/nav.goto_reward_page` 只关 y<400 的 X；游戏计划在遮罩下点入口。弹窗从 18:02 一直挂到 18:39 |
| 18:40 | 外部 App 失败 | 当天第一次进奖励页弹出「签到成功，获得10赠币 / 看视频额外领 / 我知道了」。`ExternalRewardPageReady` 只认「今日已获赠币」，弹窗下照样命中，`ExternalScrollToDianping` 在弹窗上空滑 14 次 |

| 模块 | 修改 |
| --- | --- |
| 新增 `qqreader/page/blocking_popup.py` | `find_blocking_popup(boxes)`：签到弹窗（「签到成功」+「我知道了」）→ 点「我知道了」，不点「看视频额外领」；居中运营海报按版式识别——屏幕中部（水平偏离中线 ≤40、y 300～1150）单独的 X，正上方 40～320 像素有居中的短按钮文案 → 点 X。不依赖活动文案（同一活动也会以横幅出现在书城页）。`may_have_blocking_popup(texts)` 供只有文字的地方预检 |
| `qqreader/runner/handoff.py` | 新增 `FrameKind.BLOCKING_POPUP`，排在验证码 / 确认框 / 挽留弹窗之后、书架之前；点 OCR 看到的关闭按钮后重新截图确认 |
| `scripts/auto_read_30min.py` | `classify_page` 有弹窗时返回「弹窗」而不是「书架」；`dismiss_blocking_dialogs` 先关每日弹窗（升级 / 退出确认框叠在上面时仍先点它的「取消」） |
| `qqreader/reward/nav.py` | `goto_reward_page`、`find_watch_entry`、`back_to_reward` 在确认页面前先关每日弹窗；新增 `dismiss_blocking_popup(client)` |
| `qqreader/tasks/game.py`、`scripts/run_task.py` | 游戏适配器接收 `navigation_client`：HOME / REWARD_HOME / GAME_ENTRY 下 OCR 预检到 X 或「签到成功」时重新截图，点关闭按钮，下一步重新观测；同一弹窗最多点 3 次后交回原流程 |
| `scripts/run_task.py::_apply_external_checkin_popup_overrides` | 外部 App 运行时覆盖新增节点 `ExternalCheckinPopupDismiss`（OCR `^我知道了$`，ROI `[180,690,360,140]`，max_hit 3），排在 `ExternalOpenRewardFromShelf` / `ExternalRewardPageReady` / `ExternalScrollToDianping` / `ExternalBackUntilRewardOrShelf` 的 next 最前 |

**改动文件**：上表各文件；`tests/test_daily_popups.py`（17 项）、`tests/fixtures/daily_popup_ocr_frames.json`（6 帧真实 OCR：书架海报、签到弹窗、弹窗关闭后的书架、普通奖励页，以及两个反例——书城横幅上的同款活动文案、奖励页偏离中线的 X）；本日志。
**验证**：
- 识别离线回放：`maafw*.log` 全部 10207 帧真实 OCR 中，命中的只有签到弹窗（09-22、09-23、09-28）、书架运营海报（09-24「中秋找玉兔」、09-27「现金红包」、09-28「秋日豪礼」）；09-28 当天 1446 帧书架海报、179 帧签到弹窗全部命中，其余帧 0 误中。
- 新测试先写：接入前 15 项中 9 项失败（识别函数 6 项通过）；之后补的外部 App 覆盖、升级框优先 2 项未在修复前单独跑过。修复后 17 项全部通过。全量 `py -3.10 -m pytest`：441 passed、4 failed、3 skipped；4 项失败是 master 上原有的已知失败（广告等待 40/35 秒 ×2、直播退出、`live_sendevent` 未入库），在分支 `claude/known-test-failures-20260929` 另行修复。
- **未实机验证**：两类弹窗每天只在跨天后 / 第一次进奖励页出现，需等下一次每日运行自然触发。
**未覆盖 / 遗留**：旧 pipeline 任务（外部 App、听书、等级广告）运行中途才弹出的书架海报只靠下一次交接检查关闭，pipeline 内没有加 X 节点（「我的」页有图标会被 OCR 成 X，Maa 节点无法同时校验按钮文案）；广告任务的 `AdTaskAdapter` 通过 `reward/nav` 覆盖，未单独加适配器级处理；奖励页偏离中线的 X（09-22/09-26 各一帧，性质未确认）保守不点。
**分支**：`claude/daily-popup-dismiss-20260929`
**回滚**：`git log --oneline -S "关闭书架每日运营弹窗与奖励页签到弹窗" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-09-27 · GUI 实机验证模拟器地址 / 书名 / 封面，修正截取对话框说明被截断

**触发**：用户要求实际操作并实机验证上一条的新功能（合并后的 `master`，`启动QQReaderGUI.cmd` 启动 GUI，通过桌面操作点击）。

| 验证项 | 结果 |
| --- | --- |
| 「扫描」 | 依次 `adb connect` 16384/16416/16448/16480，结果「127.0.0.1:16384（在线）」 |
| 「截取…」 | 模拟器停在书架，对话框显示 720×1280 截图；拖动框选《全职法师》封面，选区 x=30 y=414 92×130，保存到 `runtime/covers/audiobook_cover_20260927_173246.png`，「听书封面」自动填入，队列摘要显示「《全职法师》· 封面」 |
| 地址覆盖 | 界面选 `localhost:16384`（同一台模拟器的另一种写法）后「直接运行已选」：本轮 Maa 日志中设备地址 151 次均为 `localhost:16384`、0 次 `127.0.0.1:16384`，说明三个任务进程都用了界面选择；验证后点「跟随配置」并 `adb disconnect localhost:16384` |
| 1 分钟试跑 | run `daily_20260927_233314_e4d1416a`：每日自动阅读 成功 01:47（`--book-title 宇智波`，OCR 点中《宇智波：从扉间人柱力开始》）→ 每日游戏 成功 02:48 → 每日听书 成功 01:39（`--book-title 全职法师 --cover-image …173246.png`，`AudiobookFindBook` 命中）；pipeline md5 前后一致，封面模板已删除 |
| GUI 截取的封面 | 用 Maa TemplateMatch 在书架实拍上匹配：命中 (30,414,92,130)，score 1.0，与 OCR 标题「全职法师」(133,442) 同一行 |

| 模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| `qqreader/gui/app.py::CoverCaptureDialog` | 截取对话框顶部说明右侧被截断 | 说明 `wraplength=400`，而对话框宽度由 360px 画布决定 | 改为 340 |

**改动文件**：`qqreader/gui/app.py`、`tests/test_book_device_selection.py`（新增 `test_cover_dialog_hint_fits_canvas`，改回 400 时失败）、本日志。
**验证**：全量 424 passed、4 failed（与基线相同的 4 项已知失败）、3 skipped（环境原因）。修正后的对话框未重新实机打开。
**未覆盖 / 遗留**：试跑中听书是书名先命中，封面节点这一轮没有轮到（封面路径已在上一条的命令行实跑中验证）；自动阅读选其他小说、听书“不换书且找不到”仍只由单元测试覆盖；实机操作时误启动过一个 `python -m pydoc -b`，已按 PID 结束。
**分支**：`claude/cover-dialog-wrap-20260927`
**回滚**：`git log --oneline -S "GUI 实机验证模拟器地址" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-09-27 · 两账号实机验收通过，发布 v2026.09.27-handoff-guard

**触发**：QQR-53 / 54 / 55 与「GUI 可选择模拟器地址、自动阅读小说，以及听书书名与封面」已于本机 17:14 合并进本地 `master`（`e22828d`、`91ecff0`）。用户随后在两个账号上用 GUI 跑每日流程，确认正常后要求推送、合并并发布 Release。

| 运行 ID（北京时间） | 任务与结果 |
| --- | --- |
| `daily_20260927_233314_e4d1416a` | 自动阅读 → 游戏 → 听书，3 项全部成功，流水线 `SUCCEEDED`；第 2、3 项启动前的交接检查均为 READY（返回 1 次） |
| `daily_20260928_000449_dad048be` | 自动阅读 ×2 → 游戏 → 广告 → 等级广告 → 听书，6 项全部成功，流水线 `SUCCEEDED`；第 2～6 项启动前交接检查均为 READY（返回 1～2 次） |

第二个账号的等级广告（`runtime/logs/maafw.log`）：`AdCountdown` 按完整文案「观看N秒，可获得奖励」命中，等到倒计时结束；`AdBrowseOfferModal` 没有命中（没有提前关闭广告）；最后命中积分行「今日已完成」。

**改动文件**：本日志。
**验证**：发布分支（内容等于本地 `master` `91ecff0`）全量 `py -3.10 -m pytest` 结果写在合并提交说明里。两次实机运行时，主检出里还有另一个会话未提交的 QQR-39 改动（`qqreader/runner/runner.py`），**不在本次发布内**。
**未覆盖 / 遗留**：验证码阻塞、QQR-54 的截断倒计时（「观看20秒」）和「继续观看 / 放弃奖励」挽留弹窗，实机都没有出现，仍只由单元测试和真实 OCR 回放测试覆盖；交接失败 → 跳过下一项的分支实机未出现；`dist/QQReaderGUI.exe` 未重建（启动脚本运行源码）。
**分支**：`claude/release-handoff-guard-20260927` → `master`（`--no-ff`）；合并前保护点 `backup/20260927-before-release-merge`；标签 `v2026.09.27-handoff-guard`、`verified/20260927-qqr53-55`。
**回滚**：`git log --oneline -S "两账号实机验收通过，发布" -- CHANGELOG.md` 找到后，定位对应的合并提交，执行 `git revert -m 1 <合并提交>`；功能回滚分别 revert `e22828d`、`91ecff0`（均为合并提交，用 `-m 1`）。

---

## 2026-09-27 · GUI 可选择模拟器地址、自动阅读小说，以及听书书名与封面

**触发**：用户要求在 GUI 里选择模拟器地址和小说，听书可以选择书名和封面。此前模拟器地址只能改配置（且会被启动脚本回写），阅读书目是 `auto_read_30min.py` 的常量，听书书目写死在本机 pipeline，找不到时还会打开书架第一本。

| 模块 | 修改 |
| --- | --- |
| GUI 标题栏（`qqreader/gui/app.py::_build_device_selector` 等） | 新增「模拟器」下拉框 + 应用 / 扫描 / 跟随配置。候选：配置地址、MuMu 12 多开默认端口 16384/16416/16448/16480、`adb devices` 在线设备；可手动输入。选择存到 `runtime/gui_device.json`，子进程通过环境变量 `QQREADER_ADB_ADDRESS` 覆盖（加载器原本就支持），不改配置文件——`启动QQReaderGUI.cmd` 每次启动会写回 MuMu 实例 0 的端口。任务运行中不能切换 |
| `qqreader/gui/device.py`（新增） | 地址校验、`adb devices` 解析、候选排序、选择持久化、子进程环境 |
| 任务参数（`qqreader/gui/task_catalog.py`） | 字段类型增加 `text` / `file`；自动阅读增加「小说书名」（默认「宇智波」，多个用 `/` 分隔）；听书增加「听书书名」（默认「全职法师」）、「听书封面」（默认空）、「找不到时换书」（默认勾选，保持旧行为）；新增 `carry_over_selection`，`scripts/dynamic_plan.py` 重建计划时保留书目选择 |
| 任务详情表单 / 封面截取（`app.py::_build_detail`、`CoverCaptureDialog`；`qqreader/gui/cover.py` 新增） | 文本框、封面「选择… / 截取… / 清除」；「截取…」用 `adb exec-out screencap -p` 截当前画面，缩小显示后框选，按原尺寸裁出存到 `runtime/covers/`；尺寸不对（例如整张截图）会提示。顺带修正：详情栏窄时数字框被挤掉的布局 |
| `qqreader/gui/commands.py::build_run_task_command` | 传 `--book-title` / `--cover-image` / `--no-first-book-fallback` |
| `scripts/run_task.py` | 新参数；`BookSelection`；阅读把书名以 `--book` 传给 `auto_read_30min.py`；听书在 `_patch_legacy_pipeline` 中调用 `_apply_audiobook_book_overrides`：改写 `AudiobookFindBook.expected`（`re.escape`），有封面时复制为 `<resource>/image/gui_audiobook_cover.png` 并在各 next 列表的 `AudiobookFindBook` 后插入 TemplateMatch 节点 `AudiobookFindCover`（阈值 0.8），不换书时从所有 next 中去掉 `AudiobookOpenFirstShelfBook`；结束后恢复 pipeline、删除封面模板 |
| `scripts/auto_read_30min.py` | `--book` 参数、`parse_book_keywords`；`locate_allowed_book_ui` 按所选关键词匹配（原先写死「宇智波」）；阅读完成后领奖励改用传入的 `--config`（原先写死本机配置路径） |
| 文档 | README「书目白名单」改为「书目选择」；`docs/usage.md`、`docs/configuration.md` 补充模拟器地址和书目参数 |

**改动文件**：`qqreader/gui/app.py`、`qqreader/gui/commands.py`、`qqreader/gui/task_catalog.py`、`qqreader/gui/widgets.py`、`qqreader/gui/device.py`（新增）、`qqreader/gui/cover.py`（新增）、`scripts/run_task.py`、`scripts/auto_read_30min.py`、`scripts/dynamic_plan.py`、`tests/test_book_device_selection.py`（新增）、`README.md`、`docs/usage.md`、`docs/configuration.md`、本日志。
**验证**：新增 28 项测试（书名匹配用真实书架 OCR 帧 `autoread_shelf_frames.json`；GUI 参数 → 命令行 → `run_task` 解析 → 分发的整条链路；pipeline 覆盖；地址持久化与 `load_config` 环境覆盖；封面裁剪后模板匹配回原位置）。全量 425 passed、4 failed（与基线相同的 4 项已知失败）、1 skipped；worktree 缺 `dev/` 和旧工程目录，测试时临时建目录联接指向主检出，测完已删除。
实机（MuMu 实例 0，`127.0.0.1:16384`，命令行 `run_task.py --task DailyAudiobookFlow --minutes 1`）：
- 只读：书架截图 → 用 `cover.crop_box` 截《全职法师》封面 (32,562,88,116) → Maa `TemplateMatch` 命中同一位置，score 1.0。
- 实跑 1：书名「全职法师」+ 封面 + 不换书 → `AudiobookFindBook` 命中 (133,585)，旧流程 success，听书奖励“今日奖励已领取”，exit 0。
- 实跑 2：书名「书架上没有这本书」+ 同一封面 + 不换书 → 书名未命中，`AudiobookFindCover` 命中 (32,419)（刚听过，《全职法师》已移到书架第一位，同帧 OCR 标题在 y=442），播放页 OCR 为「全职法师 / AI朗读」，exit 0。
- 两次运行后 `qq_reader_trial.json` md5 与运行前一致（`7a261df0…`），`gui_audiobook_cover.png` 已删除。
- GUI：本机构建窗口截图检查布局；切换 / 恢复模拟器地址由脚本调用界面方法验证。
**未覆盖 / 遗留**：「截取…」对话框的鼠标框选和「扫描」按钮没有人工点击验证（裁剪与解析逻辑有单元测试，截图函数在实机调用过）；自动阅读选其他书只由单元测试覆盖（没有实机去读别的书）；听书“不换书且书名、封面都找不到”时由 `AudiobookBackUntilShelf` 返回 8 次后失败，只由单元测试覆盖 pipeline 结构，实机未触发；模拟器地址覆盖只作用于 GUI 启动的子进程，`调试QQReader.cmd` 仍用配置文件；GUI 改动后未重建 `dist/QQReaderGUI.exe`。
**分支**：`claude/simulator-novel-selection-20260927`（基于未合并的 `claude/qqr-55-reading-shelf-20260927`，GUI 已在该分支上重写，合并需先合它）
**回滚**：`git log --oneline -S "GUI 可选择模拟器地址、自动阅读小说" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-09-27 · 实机极端场景测试：去掉交接检查与自动阅读中的三处盲点（QQR-53 / QQR-55）

**触发**：用户要求设计极端场景并实机测试。MuMu 实例 0（`127.0.0.1:16384`），用 worktree 新代码直接运行 `scripts/run_task.py --task HandoffCheck` 和 `scripts/auto_read_30min.py`，没有经过主检出的旧 GUI。

| 场景 | 实机结果 |
| --- | --- |
| S1 冷启动开屏阶段（OCR 为空） | READY，20 秒：返回 → 退出确认框点「取消」→ 书架 |
| S2 App 被强杀、停在桌面 | READY，41 秒：返回 4 次无效 → 重启 App → 退出确认框点「取消」→ 书架 |
| S3 正文页（FLAG_SECURE，截图 0 字节） | READY，25 秒：只按返回，不点击 |
| S4a 书城 → 排行榜二级页 | **修复前 UNSAFE**：按固定坐标 (89,1262) 连点 16 次（落在空白处，未造成副作用）；**修复后** READY，11 秒：返回 1 次 → 点 OCR 看到的书架 tab |
| S4b 书城 → 排行榜 → 详情 → 目录（4 层） | READY，17 秒：返回 3 次 → 书架 tab，没有碰「加书架 / 下载 / 免费阅读」 |
| S5 书架上的「确定退出QQ阅读？」 | READY，7 秒：点「取消」(538,1241)，没有点「退出」，App 仍在前台 |
| S6 书城主页 | READY，11 秒：点书架 tab 1 次 |
| S7 从书城主页启动自动阅读 1 分钟（QQR-55） | exit 0：书城 → 书架 tab → 找到《宇智波》→ 正文读满 1 分钟。**修复前**日志出现「活动弹窗未见关闭文本，已点右上角关闭位」，即在书城页盲点 (307,764)；**修复后**复测没有这一步 |
| S8 实跑「每日等级广告」，随后交接检查 | 等级广告 exit 2：赠币入口未出现，积分入口点了 3 次广告都没拉起，随后核对“今日已完成”失败——**QQR-54 的倒计时和挽留弹窗路径没有被触发**；pipeline 运行前后 md5 一致（已恢复）。随后的交接检查在等级页上返回 2 次，READY，9.6 秒 |
| S9 「我的」/「发现」tab | 均 READY，约 7 秒：返回 1 次 |

| 模块 | 问题 | 修改 |
| --- | --- | --- |
| `qqreader/runner/handoff.py` | 排行榜二级页有「男生 / 女生」，被判为书城，然后按固定坐标盲点书架 tab，而且无限重复 | 去掉 `SHELF_TAB_FALLBACK`，只有 OCR 在底部导航区实际看到「书架」才判为书城并点它，否则按其他页面返回；新增 `_targeted_action`，同一页面类型上的定向点击连续 2 次无效后改走返回 / 重启（重启后重新计数） |
| `scripts/auto_read_30min.py::go_to_shelf_tab` | 固定坐标 (89,1242) 盲点 | 只点 OCR 看到的底部「书架」tab，看不到就不点 |
| `scripts/auto_read_30min.py::dismiss_blocking_dialogs` | 书城横幅「勋章/装扮限时返场」「免费读一年」被当成活动弹窗，盲点 (307,764) 或页面上的任意「X」；很可能就是 QQR-55 现场 05:50:04“点 X 后跳到书城”的原因 | 确认是书城页时，活动文案不算弹窗；`DISMISS_TEXTS` 由 set 改为有序 tuple，「取消」优先于「X」（set 的遍历顺序随进程哈希随机） |

**改动文件**：`qqreader/runner/handoff.py`、`scripts/auto_read_30min.py`、`tests/test_qqr53_handoff.py`、`tests/test_qqr55_reading_shelf.py`、`tests/fixtures/handoff_ocr_frames.json`（新增 2 帧实机 OCR：排行榜二级页、书城主页）、本日志。
**验证**：新增 5 项回归测试（排行榜二级页不盲点、同一定向点击不无限重复、自动阅读二级页不点书架、书城横幅不算弹窗、升级弹窗先点取消）；全量 396 passed、4 failed（与基线相同）、2 skipped。实机结果见上表，交接证据截图在 `runtime/screenshots/handoff/`。
**未覆盖 / 遗留**：验证码场景无法人为触发，只由单元测试覆盖；QQR-54 实机未触发（广告没拉起）；积分广告点了不拉起的原因未查（可能与“今日获得29积分”的上限有关，也可能是广告推荐隐私政策提示，需要单独确认，不能替用户同意协议）；App 不在前台时交接检查仍会先白按 4 次返回才重启（约 8 秒，可优化）；`find_text` 对「X」是子串匹配，会命中 “HIXAXHSOH” 这类文字，本次只调整了优先级；串行调度（GUI 先交接检查再启动下一项）的整链只由故障注入单元测试覆盖，实机是手动分步执行的。
**分支**：`claude/qqr-55-reading-shelf-20260927`
**回滚**：`git log --oneline -S "实机极端场景测试：去掉交接检查" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-09-27 · 自动阅读不再把书城排行榜页当成书架（QQR-55）

**触发**：每日批次 `daily_20260927_114947_a58b6564` 第一轮 35 分钟阅读启动约 25 秒后 exit 3。`runtime/logs/auto_read.log` 05:50:12 记“已返回书架”，05:50:13 的 OCR 却是书城排行榜。用 `maafw.bak.2026.09.27-07.03.17.990.log` 第 15300～16261 行逐帧还原：05:50:02 画面是书架 + 活动弹窗，点 X 后变成书城 + 升级弹窗，点「取消」和 X 后一直停在书城；05:50:12 那帧书城页被 `is_on_shelf()` 判成书架。

| 模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| 书架判定 | 书城排行榜页被确认成书架 | `SHELF_ONLY_MARKERS` 里的子串 `"章/"`（本意是进度行「84章/372章」）误中书城活动横幅 **「勋章/装扮限时返场」** | `scripts/auto_read_30min.py`：进度行改为正则 `\d+章/\d+章`；新增 `classify_page()`，命中 ≥2 个书城标记（男生 / 排行榜 / 本周强推 / 今日必读 / 高分必读）即判为书城；`is_on_shelf()` 改用它 |
| 回书架 | 书城页上按返回只会弹「确定退出」 | — | `return_to_shelf()`：确认是书城页时直接点底部「书架」tab 并重新确认 |
| 入口校验 | 白名单预检失败立即 exit 3，不区分“不在书架”和“书架上没有这本书” | `main()` 只做一次 `locate_allowed_book_ui()` | 新增 `confirm_allowed_book_on_shelf()`：先确认书架（最多 3 次，每次回书架后重新截图）；确认在书架但没有白名单书 → 仍 exit 3，白名单不放宽；始终确认不了书架 → `RuntimeError`，exit 2。两种失败都用 `record_page_evidence()` 记录页面类型、完整 OCR，并截图到 `screenshots/auto_read/` |
| 交接检查 / 退出码说明 | 同一子串判据 | — | `qqreader/runner/handoff.py` 的书架判定改用同一正则；`exit_codes` 中 3 的说明改为“致命错误或书源白名单拒绝” |

**改动文件**：`scripts/auto_read_30min.py`、`qqreader/runner/handoff.py`、`qqreader/runner/exit_codes.py`、`tests/test_qqr55_reading_shelf.py`（新）、`tests/fixtures/autoread_shelf_frames.json`（新，2 帧真实 OCR：05:50:12 被误判的书城页、05:50:27 真实书架）、本日志。
**验证**：`tests/test_qqr55_reading_shelf.py` 7 项通过：真实书城帧判为书城、真实书架帧判为书架；「勋章/装扮限时返场」不算进度行；书城 → 只点书架 tab → 确认后才找到白名单书，不点任何书；确认在书架但没有目标书时抛 `BookNotAllowed`，并记录完整 OCR；一直是书城时抛普通 `RuntimeError`，页面类型、OCR、截图都有记录。原有 `test_autoread_book_guard.py` 10 项仍通过。全量 391 passed、4 failed（与基线相同）、2 skipped。**未实机验证**（需要 GUI 从相同起点单跑「每日自动阅读」）。
**未覆盖 / 遗留**：05:50:04 点活动弹窗 X 后页面为什么从书架跳到书城，日志不足以确定（可能点到了弹窗下的元素，也可能是 App 自己切的 tab），本次没有修改 `dismiss_blocking_dialogs`。Issue 里“每轮记录实际累计阅读时长”没有做：串行记录已按轮次分别记录状态和耗时，第一轮失败不会被第二轮覆盖，但还没有“正文页累计分钟”字段。
**分支**：`claude/qqr-55-reading-shelf-20260927`（基于 `claude/qqr-54-level-ad-retention-20260927`）
**回滚**：`git log --oneline -S "自动阅读不再把书城排行榜页当成书架" -- CHANGELOG.md` 定位后 `git revert <hash>`。

---

## 2026-09-27 · 等级页广告：识别截断的倒计时，挽留弹窗点「继续观看」（QQR-54）

**触发**：GUI 批次 `daily_20260927_114947_a58b6564`，`DailyLevelAdFlow` 07:03:13 失败，留下的广告弹窗又拖垮了听书。逐帧核对 `runtime/logs/maafw.bak.2026.09.27-07.03.17.990.log` 第 26519～28318 行的 OCR 结果。

| 模块 | 现象 | 根因 | 修改 |
| --- | --- | --- | --- |
| 倒计时识别 | 07:02:30～33 广告仍在倒计时（OCR「观看20秒」「前观看17秒」），链路却去关广告 | `AdCountdown` 只认 `观看.*秒.*可获得奖励`，截断的倒计时认不出；`AdBrowseOfferModal` 的「了解详情 / 跳转详情页或第三方应用」在普通视频广告上也有，于是倒计时中点了左上角 ×，触发挽留弹窗 | 等级广告覆盖里 `AdCountdown.expected` 增加 `观看\s*\d+\s*秒`（不会匹配弹窗正文「观看视频30秒」）；所有 next 列表里 `AdCountdown` 排到 `AdBrowseOfferModal` 之前 |
| 挽留弹窗 | 07:02:36 起弹窗停留 37 秒，返回 8 次无效后失败 | 调查结论修正了 Issue 的说法：弹窗是提前关闭造成的；`AdBrowseOfferModal` / `AdCloseByBackKey` / `AdBackUntilRewardOrShelf` 等节点的 next 都没有弹窗分支 | `scripts/run_task.py::_apply_level_ad_retention_overrides`：新增 `LevelAdRetentionContinue`（点「继续观看」，最多 3 次）和 `LevelAdRetentionGiveUp`（之后点「放弃奖励」，回等级页走原有的换广告重试和“今日已完成”核对）；插入 8 个关闭/返回/倒计时节点的 next，位置在验证码节点之后、其余节点之前。该函数放在覆盖函数末尾执行，避免被 `AdStaticDownloadClose` 的重建冲掉 |

**改动文件**：`scripts/run_task.py`、`tests/test_qqr54_level_ad_retention.py`（新）、`tests/fixtures/level_ad_ocr_frames.json`（新，3 帧真实 OCR）、本日志。
**验证**：`tests/test_qqr54_level_ad_retention.py` 9 项通过：用本机真实 pipeline 加覆盖，再按 MaaFW next 顺序模拟识别真实 OCR 帧。先复现原链：弹窗上只会落到返回键节点，截断倒计时会命中 `AdBrowseOfferModal`。修复后：倒计时帧从 4 个入口都停在 `AdCountdown` 等待；弹窗帧从 8 个入口都点真实「继续观看」框 (291,754,133,39)；3 次后改点「放弃奖励」(299,840,119,37)；验证码节点仍排在最前；可重复应用、无悬空引用。全量 384 passed、4 failed（与基线相同）、2 skipped。**未实机验证**。
**未覆盖 / 遗留**：模拟器不评估 TemplateMatch（验证码模板）和 MaaFW 的 timeout / on_error 细节，实机行为仍需 GUI 单跑「每日等级广告」确认。赠币卡没有像积分卡那样的“今日已完成”核对：我手上没有赠币卡完成状态的真实截图，没有贸然加判定，本条仍需补。覆盖只在 `DailyLevelAdFlow` 启动时注入，`DailyAdFlow`（新流程）不受影响。
**分支**：`claude/qqr-54-level-ad-retention-20260927`（基于 `claude/qqr-53-handoff-20260927`）
**回滚**：`git log --oneline -S "等级页广告：识别截断的倒计时" -- CHANGELOG.md` 定位后 `git revert <hash>`。

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
