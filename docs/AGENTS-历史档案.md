# 历史档案（从 AGENTS.md 迁出）

迁出时间：20260915_190255，原文件备份：AGENTS.md.bak-20260915_190255

---

### 3.10 旧工程审计结论（QQR-1，静态审计）

> 完整报告：`docs/audits/QQR-1-old-project-audit.md`（含 pipeline 全量写死值表、逐条 `文件:行号`、证据索引）。
> 审计日期：2026-09-09；`G:\project_X` 只读；未运行真实任务、未修改旧仓库。
> 行号约定：`P(dev):行` = `dev/resource/pipeline/qq_reader_trial.json`（GUI 实际加载，SHA256 `2A469453C18BCE2BEE35CD49EB77E8A45B6C2E072A9DFE6F34FF4F659525B193`，2520 行/223 节点）。`assets` 副本审计期间被其他 issue 修改并分叉（2636 行/232 节点），仅在报告里另列。
> 本次 QQR-1 完成原清单第 1、2 项；第 3、4 项（每日结尾验证资源、旧资源整体有效性）需要另立审计/实机截图，本文只记录与验证码和写死值直接相关的部分。

#### A. 验证码调用链审计（结论）

**A1. `TencentSliderSolver` 是死代码；真正被调用的是 `tools/slide_captcha_solver.py`。**
- `third_party/TencentSliderSolver/process_current_captcha.py` 在旧仓库没有任何 import / subprocess / 配置引用；它只是独立 URL/CSS 分析脚本。
- `slide_captcha_solver.py` 的调用者只有：GUI watcher（`GUI:1678-1694, 1791-1824`）、独立 supervisor `run_ad_with_captcha.py`（`SUP:197-228, 704, 729`）、`captcha_guard` 默认工厂（`GUARD:276-300, 575-597`）。
- **纯 pipeline / MaaPiCli / `run_maa_ad.py` 链路上没有任何 solver 调用**：`run_maa_ad.py` 只做 `MaaTaskerPostTask`（`RUNNER:117-119`）；pipeline 里唯一的验证码节点是图片模板 `AdCaptchaDetected`（`P(dev):1770-1781`），没有滑块节点。

**A2. 入口条件、模板、ROI、截图、渲染方式。**
- 模板 `qq_reader_captcha_prompt.png`（65x240，OCR `请在下图依次点击：`）是图片点选提示，不是滑块模板；滑块页面渲染为 `安全验证` / `拖动下方滑块完成拼图`。
- `AdCaptchaDetected` 使用 `threshold: 0.8`、`roi: [40,260,640,160]`（`P(dev):1773-1779`）。真实日志中滑块页模板分数只有 `0.742927`（`maafw.bak.2026.09.07-14.28.25.187.log:4747`）和 `0.742636`（同日志 `5096`），`best_result_=null`，识别失败。ROI 覆盖了提示框/标题，**不是本次漏检主因**；主因是模板类型不对。
- ADB 截图本身正常：同日志 `4676` 中 Maa OCR 读到 `安全验证`（score 0.999907）和 `拖动下方滑块完成拼图`（score 0.999692）；另有连接/重连期的 `No available screencap method`（同日志 26494-26498），属于另一类问题。
- 旧工程没有“验证码类型”概念，只有图片模板入口；QQ 阅读换成/新增滑块渲染后，入口条件结构性失效。

**A3. Solver 成功后没有结果验证（滑块路径）。**
- `slide_captcha_solver.main()` 只设置 `swiped = swipe(...)`（`SLIDE:481-486`）；`swipe()` 返回的是 emu_mouse/Maa/adb 命令是否被接受（`SLIDE:416-430`），没有再次截图确认验证码消失。
- GUI `_solve_slide_captcha` 只看 `found && swiped`（`GUI:1811-1815`）；supervisor 主滑块分支也只看 `solve_slide_captcha()` 的返回值（`SUP:225-228, 704-705`）。
- 对比：图片点选 solver 有 `captcha_still_visible` 复核（`CLICK:647-653, 672-674`），GUI 也检查它（`GUI:1742`）。
- QQR-9 的 `CaptchaGuard.verify_cleared/handle` 有“连续 N 帧 NONE 才算消失”的验证（`GUARD:233-269, 479-538`），但当前只接在 supervisor 的 post-ad 路径（`SUP:290-316`）。

**A4. 为什么验证码出现后没有进入 Solver，而是继续执行？**
以 `maafw.bak.2026.09.07-14.28.25.187.log` 的真实事件为准：
1. 日志 `4676`：Maa OCR 已读到 `安全验证` / `拖动下方滑块完成拼图`，页面确实是滑块验证码。
2. 日志 `4747-4749`：`AdCaptchaDetected` 模板匹配 `score=0.742927 < 0.8`，`best_result_=null`，`Node.Recognition.Failed`。
3. 日志 `4751-4758`：`AdCaptchaDetected` 只是 `AdPostReturnWatch` 的 `next` 候选之一；它失败后，`AdReturnStable`（OCR）命中奖励页文案并 `Node.NextList.Succeeded`，流程继续。
4. 日志 `4786-4800`：`AdDailyRepeat` 无 `recognition`，是 `DirectHit`（`P(dev):1877-1880`），必然成功，Action 为 `DoNothing`，继续下一轮。
5. 日志 `4883-4906`：`AdDailyComplete`、`AdVideoCounterVisible`、`AdClickWatch` 识别失败后，`AdScrollToVideoCard` 也是 `DirectHit`（`P(dev):1414-1434`），必然成功并继续滑动。
6. 日志 `5094-5098`：同一页面第二次 `AdCaptchaDetected` 仍失败（`0.742636`）。
- 结论：**没有滑块节点 + 图片模板阈值不匹配 + `AdCaptchaDetected` 不是阻塞状态 + 存在无条件 DirectHit fallback**，四个条件叠加，导致 pipeline 忽略验证码继续执行。即使 `AdCaptchaDetected` 成功，下一步也是 `AdCaptchaAwaitManualSolve`（等待人工/返回奖励页，`P(dev):1783-1799`），不是自动 solver；`AdCaptchaWaitForSafeClose` 是孤儿节点，`AdCaptchaAbort` 是唯一 `StopTask`（`P(dev):1850-1852`）。
- GUI 侧同样不满足“进入 solver”的条件：图片 watcher 依赖 `AdCaptchaDetected` 成功（`GUI:1650-1651`），滑块 watcher 只监听 `screencap failed` 或 `AdClickWatch`/`AdVideoCounterVisible` 失败（`GUI:1678-1684`），是 8s 节流 / 最多 6 次的事后启发式，不是显式验证码状态。

**A5. QQR-9 现状。** `tools/captcha_guard.py` 已实现 fail-closed 检测、求解后验证、`WAITING_FOR_HUMAN`；但 GUI 没有 import 它，纯 pipeline 也没有 captcha 状态，所以它是 supervisor post-ad 路径的部分缓解，不是完整接入。

#### B. 写死值 / 失败条件审计（结论 + 关键清单）

完整逐条表见 `docs/audits/QQR-1-old-project-audit.md` §3；这里给出关键数字：

| 类别 | 旧工程关键值 | 主要位置 | 是否可配置 | 新方案建议 |
| --- | --- | --- | --- | --- |
| 广告识别重试 | `AdScrollToVideoCard:24`、`AdScrollDownRepeat:240`、`AdCountdown:120`、`AdWaitAfterSkip:60`、`AdDailyRepeat:24`、`AdBrowseOfferModal:20`、`AdCloseByBackKey:6`、`AdThirdPartyLoginPage:6`、`AdBackUntilRewardOrShelf:8`、`AdShelfScrollTop:4`、`AdScrollToTop:12` | `P(dev):1272,1338,1395,1414,1440,1467,1657,1673,1757,1877,2500` | 只能改 pipeline JSON | 按页面/动作配置 `retry.max_attempts`，不要统一 `retry N → false` |
| 游戏识别重试 | `GameBackUntilRewardOrShelf:8`、`GameScrollToPlay:4`、`GameHallRetry:4`、`GameExitBackFallback:6`、`GameBackAfterExit:4` | `P(dev):486,544,589,752,766` | 只能改 pipeline JSON | 同上；识别失败先确认页面状态 |
| 图片模板阈值 | `ReadingFindBookTerminal:0.82`、`ReadingFindBook:0.82`、`GameEnterByTemplate:0.82`、`AdCaptchaDetected/AdCaptchaAwaitManualSolve:0.8` | `P(dev):120,231,641,1770-1786` | 只能改 pipeline JSON | 每模板独立阈值；重新截图校准，记录实际 score |
| OCR 阈值 | 133 个 OCR 节点**全部没有显式 threshold**，使用 Maa 默认值；旧工程未记录默认值 | 全部 OCR 节点，如 `P(dev):15,1867,1889` | 只能改 Maa/JSON，未暴露 | 配置 `recognition.ocr_threshold`，并在日志记录实际 score |
| retry interval / count | pipeline 没有独立 interval，`post_delay` 充当间隔；GUI 广告定位 8s/8 次、滑块 8s/6 次；supervisor 图片 30 次、滑块 8s/6 次、ad locator 6s/3 次；`CaptchaGuard` 3 次/验证 4 次×1.2s/连续 2 帧 | `GUI:1662-1685`；`SUP:59-65,111,147,613-628,685-710`；`GUARD:78-83` | 否（源码常量） | 全部外置：`recovery.*.throttle/attempts`、`captcha.verify_*` |
| 页面加载等待 | `post_delay` 共 157 个节点；≥3000ms 的 27 个，例如 `LaunchQQReader:4000`、`DailyAdFlow:6000`、`GameEnterByTemplate:5000`、`ReadingWaitOneMinute:2100000`、`GameWaitOneMinute:1500000`、`AdCountdown:5000` | `P(dev):2,295,443,641,691,1197,1673` 等 | 只能改 pipeline JSON | `waits.state_settle_ms` / `waits.after_action_ms` 按状态配置 |
| 节点超时 | 仅 6 个：`GameExternalActive:60000`、`GameWaitOneMinute:1620000`、`LevelAfterCoinAd:12000`、`LevelAfterPointsAd:12000`、`AdCountdown:45000`、`ClaimDismissAddShelf:3000` | `P(dev):627,691,1132,1188,1673,2037` | 只能改 pipeline JSON | `timeouts.step` + `timeouts.task`，区分 TIMEOUT/FAILED |
| 验证码识别条件 | `AdCaptchaDetected` 模板 `qq_reader_captcha_prompt.png` / `threshold 0.8` / `roi [40,260,640,160]`；`AdCaptchaAwaitManualSolve` 同模板；`AdCaptchaWaitForSafeClose` OCR `请在下图依次点击`；关闭按钮 OCR `^[Xx×]$` + ROI `[80,850,170,190]`/`[560,380,140,150]`；固定关闭坐标 `[139,965]` | `P(dev):1770-1852` | 只能改 pipeline JSON | 显式 `captcha_condition`，按类型（click/slide/unknown）分流；求解后必须 `verify_cleared` |
| 滑块 ROI/检测 | 无 pipeline ROI；`slide_captcha_solver` 用整帧扫描 + 硬编码颜色/灰度/尺寸：蓝 `(180,50,0)..(255,220,180)`、面积≥500、宽 60..180、高 35..100；灰 180..220、长条 >40% 宽；puzzle 区域 `track_y-300..track_y-35`；缺口面积 500..25000、宽高 20..150；Canny 50/150；右边缘忽略 60px | `SLIDE:147-159,165-190,258-320` | 否 | 配置 `captcha.slide.*`；优先模板/特征模型，不要写死颜色 |
| 硬编码路径/坐标/超时 | GUI `MUMU_PATH/ADB_PATH/ADB_ADDRESS`、`G:\project_I\logs\qq_reader_final.png`；`run_maa_ad.py` `G:\project_X\dev...`；supervisor `D:\...\adb.exe`、`127.0.0.1:16384`、`REFRESH_POINT=(180,908)`；slide solver `D:\python\python.exe`；pipeline 32 个 `target`、18 个滑动 `begin/end` | `GUI:39-67`；`RUNNER:147-155`；`SUP:32-46`；`SLIDE:30-31`；`P(dev)` 3.1.6/3.1.7 | 否 | 机器配置 + 可配置坐标 fallback；不在源码写盘符/用户名/绝对路径 |
| 任务失败条件 | 旧工程没有统一 outcome；只有 `AdCaptchaAbort` 一个 `StopTask`（`P(dev):1850-1852`）；GUI 只对 `Tasker.Task.Failed`、连接失败、screencap 失败置 `run_failed`（`GUI:1628-1646`）；`AdVideoSearchExhausted`、`ClaimGameScanExhausted` 用 `DoNothing` 静默结束；33 个终端节点无 `next`/`on_error` | `P(dev):1436,1850,1889,2021`；`GUI:1628-1646`；`assets/interface.json:25-62` | 否 | 每任务显式 `success_condition` / `failure_condition` / `captcha_condition`；统一 outcome 枚举 |

**关键结构性发现**：`AdDailyRepeat`（`P(dev):1877-1880`）和 `AdScrollToVideoCard`（`P(dev):1414-1434`）没有 `recognition`，是 `DirectHit`，永远成功；`AdReturnStable` 的 OCR 在滑块弹窗上方仍能看到奖励页文案时也会成功。这就是“验证码出现后程序继续执行”的直接机制，也是新设计必须避免的：**验证码状态必须先于普通页面识别，且不能被普通 DirectHit fallback 绕过。**

#### C. 对 V1 设计的直接输入

- 每个任务必须有独立 `success_condition`、`failure_condition`、`captcha_condition`；识别不到一次或几次不等于 FAILED。
- 验证码必须是阻塞状态：`CAPTCHA_DETECTED` 优先于所有普通页面识别和 DirectHit fallback；禁止“验证码识别失败 → 当作没有验证码 → 继续”。
- 滑块验证码要进入 pipeline/状态机，不能只靠 GUI watcher；求解后必须连续多帧确认验证码消失再恢复任务。
- `max_hit`、`post_delay`、`threshold`、OCR `expected`/threshold、ROI、target/begin/end、timeout、retry interval/count 全部外置到配置模型，不写死在代码或 pipeline JSON 里。
- 固定路径、模拟器地址、ADB 端口、解释器路径放机器配置；固定坐标只作为 fallback 且必须可配置。
- 旧图片点选模板和滑块检测参数必须在当前设备重新截图/标定后才能进入 V1；不能假定旧模板仍有效。

#### D. 仍待实机确认

1. 重新制作 `qq_reader_captcha_prompt.png` 与滑块验证码模板/特征，测量实际匹配分数，标定 threshold/ROI。
2. 确认当前滑块页面的颜色、轨道、缺口布局，验证 `slide_captcha_solver.detect` 是否仍 `found=true`。
3. 确认图片点选验证码是否仍出现；旧日志 `AdCaptchaDetected` 0 次成功，不能作为模板有效的证据。
4. 确认 Maa/ADB screencap 在验证码页、广告页、FLAG_SECURE 正文页的实际行为，校准黑屏阈值。
5. 确认求解后验证的截图时机/连续帧数/刷新行为；滑块主路径当前没有验证。
6. 确认 `CaptchaGuard` 如何接入 pipeline/GUI；V1 目标是“关键操作前检测 → CAPTCHA_DETECTED 阻塞 → solver → verify_cleared → 恢复”。

