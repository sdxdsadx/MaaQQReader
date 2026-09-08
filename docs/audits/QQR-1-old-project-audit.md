# QQR-1 旧工程审计：验证码调用链 + 写死值/失败条件清单

- 审计日期：2026-09-09
- 审计对象：`G:\project_X`（只读）
- 审计方式：静态读取 + 既有日志/截图离线分析；**未运行真实任务、未修改旧仓库**
- 审计快照：`C:\Users\26142\AppData\Local\Temp\qqr1_snapshot_20260909`
- 行号约定：`P(dev):行` = `G:\project_X\dev\resource\pipeline\qq_reader_trial.json`；`P(assets):行` = `G:\project_X\assets\resource\pipeline\qq_reader_trial.json`；`GUI:行`、`SUP:行`、`SLIDE:行`、`CLICK:行`、`GUARD:行`、`RUNNER:行`、`LOC:行` 同理。

> 重要：审计期间旧仓库的 `assets/resource/pipeline/qq_reader_trial.json` 被其他改动更新（2636 行、232 节点），而 GUI 实际加载的 `dev/resource/pipeline/qq_reader_trial.json` 仍是 2520 行、223 节点。本报告以 **dev 运行时副本** 为主引用行号；`assets` 仅在 issue 明确引用或两者差异处标注。

## 0. 快照与关键文件

| 文件 | 行数/大小 | SHA256 | 说明 |
| --- | --- | --- | --- |
| `dev/resource/pipeline/qq_reader_trial.json` | 2520 行 / 73360 B | `2A469453C18BCE2BEE35CD49EB77E8A45B6C2E072A9DFE6F34FF4F659525B193` | GUI 实际加载（`GUI:47`）；本报告主行号 |
| `assets/resource/pipeline/qq_reader_trial.json` | 2636 行 / 77429 B | `4C6FDDD9C221AC25D432EC63A3B6CD3201BF0794AB8861B7D8C4C66AAA2CC57C` | issue 引用副本；审计期间被其他 issue 修改，已与 dev 分叉 |
| `gui/maa_qq_reader_gui.py` | 87594 B | `4F9A704AB8966DE12D7CDEDF625F2640D4D73CFF9D9409C32081AC6617EAC16C` | GUI 与 watcher |
| `tools/run_ad_with_captcha.py` | 36196 B | `E92C67639ADFFD77E49DAB1D2225155E4D0688DA941A19DE1B0BB04ABA00AD56` | 独立 supervisor；GUI 不调用 |
| `tools/run_maa_ad.py` | 7776 B | `A527AACAC6B098FDE8ABEC72AFCA1100F2E140566E93B39A8BC115A06D3D6EF9` | GUI 直接运行的 Maa runner |
| `tools/slide_captcha_solver.py` | 19276 B | `0F0570142BE408CE023C6878ADFA4EA861F022BE65E100F053A5205032CB3171` | 滑块求解器 |
| `tools/captcha_solver.py` | 29982 B | `2989560188AAC25DE87B6CE9E8003709C645AA34A953B8B393A9373184527B77` | 图片点选求解器 |
| `tools/captcha_guard.py` | 27004 B | `9C5F3901D32B633C9BD337A8574C580D9A864DBA805131A6B71F652796F664B2` | QQR-9 新增的 Guard；只在 supervisor 的 post-ad 路径生效 |
| `tools/ad_locator.py` | 15592 B | `076B5BD7144AF76AF7EAF08D8D69DDE538A334BACFF2F3780BD2CE08C59AA9BC` | 广告卡片定位 |
| `assets/interface.json` | 2048 B | `FD993AB9A4B246D4ADA38CD28872FC75054601E2B14336BA48D87FD2045118C2` | 任务入口；无独立任务超时字段 |

### 0.1 验证码节点 `assets` ↔ `dev` 行号对照

| 节点 | `assets` 行号（issue 引用副本） | `dev` 行号（GUI 实际加载） |
| --- | --- | --- |
| `AdCaptchaDetected` | 1886-1898 | 1770-1782 |
| `AdCaptchaAwaitManualSolve` | 1899-1916 | 1783-1800 |
| `AdCaptchaCloseFixedLeft` | 1917-1926 | 1801-1810 |
| `AdCaptchaCloseLeftButton` | 1927-1940 | 1811-1824 |
| `AdCaptchaCloseRightButton` | 1941-1954 | 1825-1838 |
| `AdCaptchaWaitForSafeClose` | 1955-1965 | 1839-1849 |
| `AdCaptchaAbort` | 1966-1969 | 1850-1853 |
| `AdReturnedAfterClose` | 1970-1975 | 1854-1859 |
| `AdPostReturnWatch` | 1976-1982 | 1860-1866 |
| `AdReturnStable` | 1983-1992 | 1867-1876 |
| `AdDailyRepeat` | 1993-2004 | 1877-1888 |

> 本报告正文以 `dev` 行号为主；需要按 issue 原文的 `assets` 路径引用时，用上表换算。`assets` 在审计期间被其他 issue 修改，节点号相同但行号会漂移。

## 1. 结论摘要

1. **`TencentSliderSolver` 是死代码**：`third_party/TencentSliderSolver/process_current_captcha.py` 是独立脚本，旧仓库中没有任何 import / subprocess / 配置引用它。真正被调用的是 `tools/slide_captcha_solver.py`。
2. **纯 pipeline / MaaPiCli / `run_maa_ad.py` 链路上没有滑块验证码节点，也没有任何 solver 调用**。pipeline 里唯一验证码节点是图片点选模板 `AdCaptchaDetected`（`P(dev):1770-1781`），滑块验证码没有识别节点。
3. **验证码出现后没有进入 solver 的直接原因**：滑块页面的模板匹配分数 `0.742927/0.742636`，低于 `AdCaptchaDetected` 的 `threshold: 0.8`，识别失败（`best_result_=null`）；失败不是阻塞状态，pipeline 继续评估 `next` 候选，`AdReturnStable`（OCR）和 `AdDailyRepeat`（DirectHit）相继成功，随后 `AdScrollToVideoCard`（DirectHit）继续滑动。日志证据见第 2.5 节。
4. **滑块求解成功后没有结果验证**：`slide_captcha_solver.main()` 只把 `swiped` 设为 swipe 命令是否下发成功（`SLIDE:481-486`）；`swipe()` 返回的是“输入命令被接受”（`SLIDE:416-430`），没有求解后再截图确认验证码消失。GUI 的 `_solve_slide_captcha`（`GUI:1791-1824`）和 supervisor 的主滑块分支（`SUP:197-228, 704-705`）也只看 `found + swiped`。图片点选 solver 则有 `captcha_still_visible` 复核（`CLICK:647-653, 672-674`；GUI:1742）。
5. **QQR-9 的 `CaptchaGuard` 已存在但接线不完整**：`tools/captcha_guard.py` 实现了 fail-closed 检测、求解后连续 N 帧确认、`WAITING_FOR_HUMAN` 状态；但它只被 `tools/run_ad_with_captcha.py` 的 `check_post_ad_captcha()`（`SUP:290-316`）使用，GUI 仍走自己的 watcher，纯 pipeline 仍没有 captcha 状态。

## 2. A. 验证码调用链审计

### 2.1 调用链总表

| 路径 | 是否调用图片 solver | 是否调用滑块 solver | 触发条件 | 触发后是否验证 | 关键证据 |
| --- | --- | --- | --- | --- | --- |
| Maa pipeline / MaaPiCli | 否 | 否 | 只有 `AdCaptchaDetected` 图片模板节点；无滑块节点 | N/A | `P(dev):1770-1781`；全 JSON 无 slider/captcha slide 节点 |
| `tools/run_maa_ad.py` | 否 | 否 | 直接 `MaaTaskerPostTask` | N/A | `RUNNER:117-119` |
| GUI | 是（仅当 `AdCaptchaDetected` recognition succeeded） | 是（启发式） | 图片：`Node.Recognition.Succeeded + name=AdCaptchaDetected`；滑块：`screencap failed` 或 `AdClickWatch`/`AdVideoCounterVisible` recognition failed，8s 节流 / 最多 6 次 | 图片：是（`captcha_still_visible`）；滑块：否 | `GUI:1647-1661`、`GUI:1678-1694`、`GUI:1742`、`GUI:1811` |
| `tools/run_ad_with_captcha.py`（独立 supervisor，GUI 不调用） | 是 | 是 | 图片：`captcha_signal` = `AdCaptchaDetected` succeeded；滑块：日志含 `安全验证` / `screencap failed` / ad-not-found，8s 节流 / 最多 6 次；post-ad：广告结束信号后 poll 10s | 图片：是（`solve_captcha` 检查 `captcha_still_visible`）；滑块主分支：否；post-ad guard：是 | `SUP:346-351`、`SUP:683-707`、`SUP:290-316` |
| `third_party/TencentSliderSolver/process_current_captcha.py` | 无调用者 | 无调用者 | N/A | N/A | 全仓库搜索无引用 |

### 2.2 A1：谁在调用、入口是否失效

- `TencentSliderSolver`：死代码。旧仓库中没有 `import TencentSliderSolver`、没有 `process_current_captcha` 引用、没有 subprocess 调用。它本身也不是类，只是一个依赖 `requests/PIL/matplotlib` 的独立 URL/CSS 分析脚本。
- `slide_captcha_solver.py` 的调用者只有三类：
  1. GUI watcher → `_solve_slide_captcha`（`GUI:1678-1694, 1791-1824`）。
  2. `tools/run_ad_with_captcha.py` → `solve_slide_captcha()`（`SUP:197-228`），调用点 `SUP:704`、`SUP:729`；`CaptchaGuard` 工厂也把它作为 `solve_slide`（`SUP:278-287`）。
  3. `tools/captcha_guard.py` 的默认工厂 `default_solve_slide()`（`GUARD:276-300`）和 `build_emulator_guard()`（`GUARD:575-597`）；但 GUI 不 import `captcha_guard`，所以该工厂在 GUI 路径不生效。
- 纯 pipeline / CLI 入口（`MaaPiCli.exe`、`run_maa_ad.py`）没有任何 captcha/solver import 或调用；`RUNNER` 只做 resource/controller/task。
- 入口条件失效的两种表现：
  1. 图片入口 `AdCaptchaDetected` 在审计日志中 **0 次成功**；09-07 日志 40 次失败，其他会话 24/133/51/24 次失败。滑块页面的模板分数最高 `0.742927`，低于阈值 `0.8`。
  2. GUI 图片 watcher 依赖 `AdCaptchaDetected` 成功（`GUI:1650-1651`），因此同一个失败会让图片 solver 也不触发；滑块 watcher 不检测 `安全验证`，只在广告按钮识别失败后启发式触发（`GUI:1678-1684`）。

### 2.3 A2：模板、阈值、ROI、截图、渲染方式

| 问题 | 结论 | 证据 |
| --- | --- | --- |
| 模板是否过期 | `qq_reader_captcha_prompt.png`（65x240，OCR `请在下图依次点击：`）仍是“图片点选”提示模板；但它不是滑块模板。审计日志没有 `AdCaptchaDetected` 成功样本，无法证明它在当前 QQ 阅读版本仍能匹配；必须重新截图校准。 | `assets/resource/image/qq_reader_captcha_prompt.png`；`P(dev):1770-1773`；日志 4747/5096 |
| 阈值 | `threshold: 0.8`；实测滑块页最高 `0.742927`（09-07 日志 4747）和 `0.742636`（5096），均低于阈值。 | `P(dev):1773`、`P(dev):1786`；日志 4747、5096 |
| ROI | `[40,260,640,160]` 覆盖 y=260..420；图片提示框实测 `[40,340,240,65]`、滑块标题 `[72,364,100,29]` 都落在 ROI 内，所以 **ROI 不是本次漏检主因**；主因是模板类型不对。滑块 puzzle/handle 在 ROI 下方，旧 pipeline 根本不看它。 | `P(dev):1774-1779`；日志 4676、4747 |
| ADB 截图 | 本次事件中正常：Maa OCR 在滑块页读到 `安全验证`（score 0.999907）和 `拖动下方滑块完成拼图`（score 0.999692）。旧工程另有连接/重连期的 `No available screencap method`（09-07 日志 26494-26498），属于另一类问题。 | 日志 4676、4753、4881、4887；`SUP:325-342`；`SLIDE:49-60, 63-98` |
| 渲染方式 | 当前页面是“蓝色滑块 + 灰色轨道 + 拼图缺口”的滑块验证码，和 `请在下图依次点击：` 的图片点选是两种渲染。旧 pipeline 没有滑块入口；`slide_captcha_solver` 用固定颜色/尺寸/灰度范围检测，颜色或布局变化就会 `found=false`。 | 日志 4676；`SLIDE:147-159, 165-190, 258-320` |

### 2.4 A3：求解成功后是否有结果验证

| 路径 | 成功判定 | 是否确认验证码消失 | 证据 |
| --- | --- | --- | --- |
| 图片点选 solver | `submitted && !captcha_still_visible` | 是 | `CLICK:647-653, 665-674`；GUI:1742；`SUP:152-156` |
| 滑块 solver CLI | `swiped` = swipe 命令是否成功 | **否** | `SLIDE:416-430, 481-486` |
| GUI 滑块 watcher | `found && swiped` | **否** | `GUI:1811-1815` |
| supervisor 主滑块分支 | `solve_slide_captcha()` 返回 swipe 结果 | **否** | `SUP:225-228, 704-705` |
| supervisor post-ad `CaptchaGuard.handle` | 连续 `verify_consecutive` 帧 `NONE` | 是 | `SUP:290-316`；`GUARD:233-269, 479-538` |
| `CaptchaGuard` 独立使用 | 同上 | 是 | `GUARD:233-269, 479-538` |

结论：**滑块 solver 本身没有 post-solve 验证**；只有 QQR-9 的 `CaptchaGuard.handle` 有验证，而它当前只接在 supervisor 的 post-ad 路径，GUI 和纯 pipeline 都不走。

### 2.5 A4：为什么验证码出现后程序没有进入 Solver，而是继续执行

以 `G:\project_X\dev\debug\maafw.bak.2026.09.07-14.28.25.187.log`（稳定轮转日志）中的一次真实事件为例：

| 日志行 | 事件 | 说明 |
| --- | --- | --- |
| 4676 | OCR 读到 `安全验证` [72,364,100,29]、`拖动下方滑块完成拼图` [72,406,272,28] | Maa/ADB 截图正常；页面是滑块验证码 |
| 4747-4749 | `AdCaptchaDetected` TemplateMatch `score=0.742927`，`best_result_=null`，`Node.Recognition.Failed` | 模板入口漏检；阈值 0.8 |
| 4751-4758 | `AdReturnStable` OCR 成功（OCR 结果里同时含奖励页文案和滑块文案），`Node.NextList.Succeeded` | 漏检后没有阻塞，pipeline 继续评估候选；奖励页文案仍可见，于是命中 |
| 4786-4797 | `AdDailyRepeat` DirectHit 成功，Action `DoNothing` | 无条件 fallback 节点成功，流程继续 |
| 4883-4906 | `AdDailyComplete`、`AdVideoCounterVisible`、`AdClickWatch` 识别失败；`AdScrollToVideoCard` DirectHit 成功 | 广告按钮被验证码遮挡，但 DirectHit 滑动节点仍成功，于是继续滑动 |
| 5094-5098 | 第二次 `AdCaptchaDetected` 仍失败，`score=0.742636` | 仍然没有进入 solver |

**直接答案**：

1. 纯 pipeline / CLI 路径没有滑块 solver 调用点；唯一 captcha 节点是图片模板 `AdCaptchaDetected`。
2. 滑块页面的模板分数 `0.742927/0.742636 < 0.8`，`AdCaptchaDetected` 识别失败。
3. `AdCaptchaDetected` 只是 `next` 列表里的一个候选，不是阻塞状态；它失败后 pipeline 继续匹配后面的候选。`AdReturnStable`（OCR）和 `AdDailyRepeat`（DirectHit）命中，所以流程继续。
4. GUI 的图片 watcher 也依赖 `AdCaptchaDetected` 成功；滑块 watcher 只监听 `screencap failed` 或 `AdClickWatch`/`AdVideoCounterVisible` 失败，8s 节流 / 最多 6 次，属于事后启发式；本次日志里它没有改变“pipeline 已经继续”的事实。
5. 即使 `AdCaptchaDetected` 成功，pipeline 的下一步也是 `AdCaptchaAwaitManualSolve`（等待人工/返回奖励页），不是自动 solver；`AdCaptchaWaitForSafeClose` 是孤儿节点，`AdCaptchaAbort` 是唯一 `StopTask`。

### 2.6 QQR-9 现状与剩余缺口

- `tools/captcha_guard.py` 已实现：`classify_frame` fail-closed（检测器异常 → `UNKNOWN`，不是 `NONE`，`GUARD:189-230`）；`verify_cleared` 连续 N 帧 `NONE`（`GUARD:233-269`）；`handle` 求解后验证、失败进 `WAITING_FOR_HUMAN`（`GUARD:479-538`）；默认验证参数 4 次 / 1.2s / 连续 2 帧（`GUARD:78-83`）。
- 但接线仍不完整：GUI 没有 import `captcha_guard`；GUI 仍用 `_solve_captcha`/`_solve_slide_captcha` 两个独立线程（`GUI:1647-1694, 1699-1824`）；纯 pipeline 仍只有 `AdCaptchaDetected` 图片模板节点；`AdCaptchaWaitForSafeClose` 仍无人引用。
- 因此 QQR-1 的根因结论仍成立；QQR-9 是 **部分缓解**（仅 supervisor post-ad 路径），不是完整接入。

## 3. B. 写死值/失败条件清单

### 3.1 Pipeline 写死值（以 `P(dev)` 为准）

#### 3.1.1 `max_hit`（识别/动作重试上限，43 条）

| 行号 | 节点 | max_hit | action | recognition | post_delay |
| --- | --- | --- | --- | --- | --- |
| 15 | LaunchDismissIKnow | 3 | Click | OCR | 1200 |
| 23 | LaunchDismissCancel | 3 | Click | OCR | 1000 |
| 31 | LaunchDismissLater | 3 | Click | OCR | 1000 |
| 39 | LaunchDismissSkip | 3 | Click | OCR | 1200 |
| 174 | ReadingDismissDownloadedUpdate | 2 | Click | OCR | 1200 |
| 202 | ReadingBackUntilShelf | 8 | ClickKey |  | 1200 |
| 331 | AudiobookBackUntilShelf | 8 | ClickKey |  | 1200 |
| 486 | GameBackUntilRewardOrShelf | 8 | ClickKey |  | 1200 |
| 544 | GameScrollToPlay | 4 | Swipe |  | 1000 |
| 589 | GameHallRetry | 4 | Click | OCR | 5000 |
| 752 | GameExitBackFallback | 6 | ClickKey |  | 1500 |
| 766 | GameBackAfterExit | 4 | ClickKey |  | 1200 |
| 808 | ExternalBackUntilRewardOrShelf | 8 | ClickKey |  | 1200 |
| 843 | ExternalScrollToDianping | 14 | Swipe |  | 1200 |
| 915 | ExternalBackAfterDianping | 4 | ClickKey |  | 1200 |
| 935 | ExternalScrollToBaidu | 8 | Swipe |  | 1000 |
| 1001 | ExternalBackAfterBaidu | 4 | ClickKey |  | 1200 |
| 1039 | LevelBackUntilHome | 8 | ClickKey |  | 1200 |
| 1087 | LevelScrollToCoinAd | 12 | Swipe |  | 1000 |
| 1146 | LevelScrollToPointsAd | 8 | Swipe |  | 900 |
| 1224 | AdStartupDismissIKnow | 2 | Click | OCR | 1200 |
| 1232 | AdStartupDismissCancel | 2 | Click | OCR | 1200 |
| 1246 | AdStartupDismissLater | 2 | Click | OCR | 1200 |
| 1272 | AdBackUntilRewardOrShelf | 8 | ClickKey |  | 1200 |
| 1338 | AdShelfScrollTop | 4 | Swipe |  | 800 |
| 1395 | AdScrollToTop | 12 | Swipe |  | 800 |
| 1414 | AdScrollToVideoCard | 24 | Swipe |  | 1200 |
| 1440 | AdScrollDownRepeat | 240 | Swipe |  | 1800 |
| 1467 | AdThirdPartyLoginPage | 6 | ClickKey | OCR | 1500 |
| 1657 | AdWaitAfterSkip | 60 |  |  | 2500 |
| 1673 | AdCountdown | 120 |  | OCR | 5000 |
| 1757 | AdCloseByBackKey | 6 | ClickKey |  | 1500 |
| 1877 | AdDailyRepeat | 24 |  |  | 1000 |
| 1919 | ClaimGameBackUntilRewardOrShelf | 8 | ClickKey |  | 1200 |
| 2001 | ClaimGameScrollDown | 16 | Swipe |  | 900 |
| 2025 | ClaimBackUntilRewardOrShelf | 8 | ClickKey |  | 1200 |
| 2114 | ClaimScrollToTop | 12 | Swipe |  | 800 |
| 2171 | ClaimScrollDown | 10 | Swipe |  | 1000 |
| 2207 | PlanBackUntilRewardOrShelf | 8 | ClickKey |  | 1200 |
| 2273 | PlanScrollToTop | 12 | Swipe |  | 800 |
| 2400 | FinalEvidenceBackUntilRewardOrShelf | 8 | ClickKey |  | 1200 |
| 2467 | FinalEvidenceScrollToTop | 12 | Swipe |  | 800 |
| 2500 | AdBrowseOfferModal | 20 | Click | OCR | 1800 |

#### 3.1.2 `threshold`（模板匹配阈值，5 条）

| 行号 | 节点 | threshold | recognition | template | roi |
| --- | --- | --- | --- | --- | --- |
| 120 | ReadingFindBookTerminal | 0.82 | TemplateMatch | reading_target_uchiha_cover.png | [0, 220, 720, 960] |
| 231 | ReadingFindBook | 0.82 | TemplateMatch | reading_target_uchiha_cover.png | [0, 220, 720, 960] |
| 641 | GameEnterByTemplate | 0.82 | TemplateMatch | game_enter_button.png | [150, 850, 420, 250] |
| 1770 | AdCaptchaDetected | 0.8 | TemplateMatch | qq_reader_captcha_prompt.png | [40, 260, 640, 160] |
| 1783 | AdCaptchaAwaitManualSolve | 0.8 | TemplateMatch | qq_reader_captcha_prompt.png | [40, 260, 640, 160] |

#### 3.1.3 `timeout`（节点级超时，ms，6 条）

| 行号 | 节点 | timeout | recognition | expected | post_delay |
| --- | --- | --- | --- | --- | --- |
| 627 | GameExternalActive | 60000 | OCR | ^领币$\|远征\|破败小镇\|快醒醒\|进度\|战士武器\|战士战力\|升级战士\|提升骷髅 |  |
| 691 | GameWaitOneMinute | 1620000 |  |  | 1500000 |
| 1132 | LevelAfterCoinAd | 12000 | OCR | 用户等级\|等级福利\|当前等级\|提升等级\|赢10-99赠币\|看小视频.*积分 |  |
| 1188 | LevelAfterPointsAd | 12000 | OCR | 用户等级\|等级福利\|当前等级\|提升等级\|赢10-99赠币\|看小视频.*积分 |  |
| 1673 | AdCountdown | 45000 | OCR | 观看.*秒.*可获得奖励 | 5000 |
| 2037 | ClaimDismissAddShelf | 3000 | OCR | ^(取消\|暂不退出\|继续使用)$ | 1000 |

#### 3.1.4 `post_delay >= 3000ms`（页面加载/稳定等待，27 条）

| 行号 | 节点 | post_delay | action | recognition | next | on_error |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | LaunchQQReader | 4000 | StartApp |  | [LaunchDismissIKnow, LaunchDismissCancel, LaunchDismissLater, LaunchDismissSkip, LaunchReady] | LaunchUnknown |
| 72 | SmokeTest | 3000 | StartApp |  | [SmokeRewardPage, SmokeShelfPage, SmokeReaderPage, SmokeGamePage, SmokeUnknownPage] |  |
| 295 | ReadingWaitOneMinute | 2100000 |  |  | ReadingExitAfterTimer |  |
| 443 | AudiobookWaitOneMinute | 2100000 |  |  | AudiobookPauseAfterTrial |  |
| 563 | GameFindPlayButton | 5000 | Click | OCR | GameOpenLargestBanner |  |
| 572 | GameOpenLargestBanner | 5000 | Click |  | [GameDismissPromo, GameExternalActive, GameAcceptAgreement, GameSelectServer, GameEnterByTemplate, GameLandingReady, GameHallRetry] |  |
| 589 | GameHallRetry | 5000 | Click | OCR | [GameDismissPromo, GameExternalActive, GameAcceptAgreement, GameSelectServer, GameEnterByTemplate, GameLandingReady, GameHallRetry] |  |
| 641 | GameEnterByTemplate | 5000 | Click | TemplateMatch | GameExternalActive |  |
| 691 | GameWaitOneMinute | 1500000 |  |  | GameExitBackFallback |  |
| 797 | DailyExternalAppFlow | 5000 | StartApp |  | [ExternalBothComplete, ExternalRewardPageReady, ExternalOpenRewardFromShelf, ExternalBackUntilRewardOrShelf] |  |
| 869 | ExternalClickDianping | 6000 | Click | OCR | ExternalReturnQQAfterDianping |  |
| 889 | ExternalReturnQQAfterDianping | 3000 | StartApp |  | [ExternalRewardAfterDianping, ExternalCloseDianpingBridge, ExternalBackAfterDianping] |  |
| 960 | ExternalClickBaidu | 6000 | Click | OCR | ExternalReturnQQAfterBaidu |  |
| 974 | ExternalReturnQQAfterBaidu | 3000 | StartApp |  | [ExternalBothComplete, ExternalRewardAfterBaidu, ExternalCloseBaiduBridge, ExternalBackAfterBaidu] |  |
| 1025 | DailyLevelAdFlow | 3500 | StartApp |  | [LevelPageReady, LevelMyPageReady, LevelClickMyTab, LevelBackUntilHome] |  |
| 1108 | LevelClickCoinAd | 3500 | Click | OCR | [AdThirdPartyLoginPage, AdSkipBrowseOffer, AdContinueWatching, AdCompleted, AdCountdown, AdScrollDownRepeat] |  |
| 1165 | LevelClickPointsAd | 3500 | Click | OCR | [AdThirdPartyLoginPage, AdSkipBrowseOffer, AdContinueWatching, AdCompleted, AdCountdown, AdScrollDownRepeat] |  |
| 1197 | DailyAdFlow | 6000 | StartApp |  | [AdStartupDismissIKnow, AdStartupDismissCancel, AdStartupDismissLater, AdStartupWait, AdThirdPartyLoginPage, AdDailyComplete, AdConfirmSkipBrowse, AdSkipBrowseOffer, AdContinueWatching, AdCompleted, AdCountdown, AdClosableAfterCountdown, AdCaptchaDetected, AdRewardPageReady, AdOpenRewardFromShelf, AdShelfRewardBanner, AdBackUntilRewardOrShelf] |  |
| 1299 | AdWaitShelfReady | 3000 |  |  | [AdDailyComplete, AdRewardPageReady, AdOpenRewardFromShelf, AdShelfRewardBanner, AdBackUntilRewardOrShelf] |  |
| 1357 | AdShelfRewardBannerClick | 3000 | Click | OCR | AdRewardPageReady |  |
| 1497 | AdClickWatch | 3500 | Click | OCR | [AdThirdPartyLoginPage, AdContinueWatching, AdSkipBrowseOffer, AdCompleted, AdCountdown, AdBrowseOfferModal, AdScrollDownRepeat] |  |
| 1514 | AdVideoCounterVisible | 3500 | Click | OCR | [AdThirdPartyLoginPage, AdContinueWatching, AdSkipBrowseOffer, AdCompleted, AdCountdown, AdBrowseOfferModal, AdScrollDownRepeat] |  |
| 1673 | AdCountdown | 5000 |  | OCR | [AdThirdPartyLoginPage, AdConfirmSkipBrowse, AdSkipBrowseOffer, AdContinueWatching, AdCompleted, AdRewardIssued, AdCountdown, AdCloseAfterNormalCountdown, AdBrowseOfferModal, AdScrollDownRepeat] | AdCloseFallbackLeft |
| 1783 | AdCaptchaAwaitManualSolve | 3000 |  | TemplateMatch | [AdCaptchaDetected, AdReturnedAfterClose, AdCaptchaAwaitManualSolve] |  |
| 1839 | AdCaptchaWaitForSafeClose | 3000 |  | OCR | [AdCaptchaCloseLeftButton, AdCaptchaCloseRightButton, AdCaptchaAbort] |  |
| 1860 | AdPostReturnWatch | 4000 |  |  | [AdCaptchaDetected, AdReturnStable] |  |
| 2196 | DailyPlanScan | 3500 | StartApp |  | [PlanDismissAddShelf, PlanRewardPageReady, PlanOpenRewardFromShelf, PlanBackUntilRewardOrShelf] |  |

#### 3.1.5 `roi`（识别区域 [x,y,w,h]，31 条）

| 行号 | 节点 | roi | recognition | expected | template |
| --- | --- | --- | --- | --- | --- |
| 39 | LaunchDismissSkip | [500, 0, 220, 260] | OCR | ^跳过.*$ |  |
| 120 | ReadingFindBookTerminal | [0, 220, 720, 960] | TemplateMatch |  | reading_target_uchiha_cover.png |
| 136 | ReadingFindBookByTitleTerminal | [90, 180, 620, 900] | OCR | 宇智波.*扉间人柱力\|宇智波：从扉间人柱力开始 |  |
| 151 | ReadingOpenFirstShelfBookTerminal | [0, 0, 180, 120] | OCR | ^书架$ |  |
| 174 | ReadingDismissDownloadedUpdate | [430, 1160, 250, 120] | OCR | ^取消$ |  |
| 213 | ReadingOpenFirstShelfBook | [0, 0, 180, 120] | OCR | ^书架$ |  |
| 231 | ReadingFindBook | [0, 220, 720, 960] | TemplateMatch |  | reading_target_uchiha_cover.png |
| 248 | ReadingDismissProgressSync | [360, 1120, 360, 160] | OCR | ^取消$ |  |
| 342 | AudiobookOpenFirstShelfBook | [0, 0, 180, 120] | OCR | ^书架.*$ |  |
| 377 | AudiobookDismissProgressSync | [360, 1120, 360, 160] | OCR | ^取消$ |  |
| 475 | GameRewardEntryUnavailable | [0, 0, 180, 120] | OCR | ^书架.*$ |  |
| 499 | GameDismissAddShelf | [0, 560, 720, 720] | OCR | ^(取消\|暂不退出\|继续使用)$ |  |
| 641 | GameEnterByTemplate | [150, 850, 420, 250] | TemplateMatch |  | game_enter_button.png |
| 1051 | LevelClickMyTab | [520, 1120, 200, 160] | OCR | ^我的$ |  |
| 1232 | AdStartupDismissCancel | [430, 1080, 250, 200] | OCR | ^(取消\|暂不开启)$ |  |
| 1286 | AdDismissAddShelf | [0, 560, 720, 720] | OCR | ^(取消\|暂不退出\|继续使用)$ |  |
| 1357 | AdShelfRewardBannerClick | [0, 0, 180, 120] | OCR | ^书架$ |  |
| 1514 | AdVideoCounterVisible | [420, 150, 300, 950] | OCR | 立即观看\|看小视频再多领 |  |
| 1539 | AdClosableAfterCountdown | [0, 0, 720, 320] | OCR | ^(X\|x\|×\|✕\|✖\|关闭\|退出\|跳过\|我知道了)$ |  |
| 1559 | AdCloseAfterNormalCountdown | [0, 0, 720, 320] | OCR | ^(X\|x\|×\|✕\|✖\|关闭\|退出\|跳过\|我知道了)$ |  |
| 1609 | AdSkipBrowseOffer | [500, 0, 220, 120] | OCR | 跳过 |  |
| 1635 | AdConfirmSkipBrowse | [150, 700, 450, 300] | OCR | 坚持退出 |  |
| 1770 | AdCaptchaDetected | [40, 260, 640, 160] | TemplateMatch |  | qq_reader_captcha_prompt.png |
| 1783 | AdCaptchaAwaitManualSolve | [40, 260, 640, 160] | TemplateMatch |  | qq_reader_captcha_prompt.png |
| 1811 | AdCaptchaCloseLeftButton | [80, 850, 170, 190] | OCR | ^[Xx×]$ |  |
| 1825 | AdCaptchaCloseRightButton | [560, 380, 140, 150] | OCR | ^[Xx×]$ |  |
| 1931 | ClaimGameDismissAddShelf | [0, 560, 720, 720] | OCR | ^(取消\|暂不退出\|继续使用)$ |  |
| 2037 | ClaimDismissAddShelf | [0, 560, 720, 720] | OCR | ^(取消\|暂不退出\|继续使用)$ |  |
| 2065 | ClaimRewardEntryUnavailable | [0, 0, 180, 120] | OCR | ^书架.*$ |  |
| 2219 | PlanDismissAddShelf | [0, 560, 720, 720] | OCR | ^(取消\|暂不退出\|继续使用)$ |  |
| 2413 | FinalEvidenceDismissExit | [0, 560, 720, 720] | OCR | ^(取消\|暂不退出\|继续使用)$ |  |

#### 3.1.6 `target`（写死点击坐标/目标，32 条）

| 行号 | 节点 | target | action | recognition | expected |
| --- | --- | --- | --- | --- | --- |
| 151 | ReadingOpenFirstShelfBookTerminal | [75, 480] | Click | OCR | ^书架$ |
| 191 | ReadingLeaveRewardPage | [55, 84] | Click | OCR | 今日已获赠币\|看小视频领好礼\|玩游戏领赠币 |
| 213 | ReadingOpenFirstShelfBook | [290, 180] | Click | OCR | ^书架$ |
| 261 | ReadingOpenMenu | [360, 640] | Click |  |  |
| 270 | ReadingClickSettingsFixed | [450, 1214] | Click |  |  |
| 286 | ReadingClickAuto | [360, 1126] | Click |  |  |
| 320 | AudiobookLeaveRewardPage | [55, 84] | Click | OCR | 今日已获赠币\|看小视频领好礼\|玩游戏领赠币 |
| 342 | AudiobookOpenFirstShelfBook | [290, 180] | Click | OCR | ^书架.*$ |
| 390 | AudiobookOpenMenu | [360, 640] | Click |  |  |
| 399 | AudiobookClickListenFixed | [657, 1145] | Click |  |  |
| 429 | AudiobookClickPlayFallback | [360, 1080] | Click |  |  |
| 448 | AudiobookPauseAfterTrial | [360, 1080] | Click |  |  |
| 572 | GameOpenLargestBanner | [360, 360] | Click |  |  |
| 589 | GameHallRetry | [360, 360] | Click | OCR | 精选大作\|今日必玩推荐\|新游\|活动\|排行\|分类 |
| 609 | GameDismissPromo | [608, 356] | Click | OCR | 会员月\|游戏内充值任意金额 |
| 656 | GameLandingReady | [200, 900, 320, 180] | Click | OCR | 踏入仙途\|进入游戏\|开始游戏\|开始修炼\|创建角色\|登录游戏 |
| 672 | GameAcceptAgreement | [145, 1020, 25, 25] | Click | OCR | 我已详细阅读并同意\|用户协议.*隐私政策 |
| 697 | GameOpenFloatMenu | [675, 275, 40, 55] | Click | OCR | ^领币$ |
| 713 | GameOpenFloatSecondTap | [675, 275, 40, 55] | Click | OCR | ^领币$ |
| 904 | ExternalCloseDianpingBridge | [55, 84] | Click | OCR | \[?大众点评\]?\|该服务由大众点评 |
| 990 | ExternalCloseBaiduBridge | [55, 84] | Click | OCR | 去百度地图金币商城\|百度地图 |
| 1326 | AdShelfRewardBanner | [90, 1245] | Click | OCR | ^书架$ |
| 1357 | AdShelfRewardBannerClick | [510, 155, 180, 125] | Click | OCR | ^书架$ |
| 1485 | AdLiveCouponPopup | [361, 1168] | Click | OCR | 恭喜获得优惠券\|限时领取.*后结束 |
| 1514 | AdVideoCounterVisible | True | Click | OCR | 立即观看\|看小视频再多领 |
| 1579 | AdCouponPopup | [361, 1168] | Click | OCR | 恭喜获得优惠券\|限时领取\|立即领取 |
| 1609 | AdSkipBrowseOffer | [680, 35] | Click | OCR | 跳过 |
| 1699 | AdCompleted | [48, 70] | Click | OCR | 恭喜获得奖励\|恭喜完成任务 |
| 1728 | AdCloseFallbackLeft | [52, 112] | Click |  |  |
| 1743 | AdCloseFallbackRight | [670, 112] | Click |  |  |
| 1801 | AdCaptchaCloseFixedLeft | [139, 965] | Click |  |  |
| 2500 | AdBrowseOfferModal | [50, 70] | Click | OCR | 了解详情\|跳转详情页或第三方应用\|下载QQ浏览器\|QQ浏览器 |

#### 3.1.7 `begin`/`end`（写死滑动坐标，18 条）

| 行号 | 节点 | begin | end | duration | post_delay | max_hit |
| --- | --- | --- | --- | --- | --- | --- |
| 544 | GameScrollToPlay | [360, 980] | [360, 420] | 500 | 1000 | 4 |
| 843 | ExternalScrollToDianping | [360, 1080] | [360, 420] | 500 | 1200 | 14 |
| 935 | ExternalScrollToBaidu | [360, 1080] | [360, 500] | 500 | 1000 | 8 |
| 1087 | LevelScrollToCoinAd | [360, 1080] | [360, 400] | 500 | 1000 | 12 |
| 1146 | LevelScrollToPointsAd | [360, 1080] | [360, 520] | 500 | 900 | 8 |
| 1338 | AdShelfScrollTop | [360, 300] | [360, 1100] | 500 | 800 | 4 |
| 1395 | AdScrollToTop | [360, 300] | [360, 1100] | 500 | 800 | 12 |
| 1414 | AdScrollToVideoCard | [360, 1000] | [360, 350] | 500 | 1200 | 24 |
| 1440 | AdScrollDownRepeat | [360, 1000] | [360, 340] | 500 | 1800 | 240 |
| 2001 | ClaimGameScrollDown | [360, 1050] | [360, 360] | 500 | 900 | 16 |
| 2114 | ClaimScrollToTop | [360, 300] | [360, 1100] | 500 | 800 | 12 |
| 2171 | ClaimScrollDown | [360, 1050] | [360, 330] | 500 | 1000 | 10 |
| 2273 | PlanScrollToTop | [360, 300] | [360, 1100] | 500 | 800 | 12 |
| 2305 | PlanScrollPage1 | [360, 1050] | [360, 330] | 500 | 1000 |  |
| 2325 | PlanScrollPage2 | [360, 1050] | [360, 330] | 500 | 1000 |  |
| 2345 | PlanScrollPage3 | [360, 1050] | [360, 330] | 500 | 1000 |  |
| 2365 | PlanScrollPage4 | [360, 1050] | [360, 330] | 500 | 1000 |  |
| 2467 | FinalEvidenceScrollToTop | [360, 300] | [360, 1100] | 500 | 800 | 12 |

#### 3.1.8 `on_error`（显式错误转移，10 条）

| 行号 | 节点 | on_error | action | recognition | next |
| --- | --- | --- | --- | --- | --- |
| 2 | LaunchQQReader | LaunchUnknown | StartApp |  | [LaunchDismissIKnow, LaunchDismissCancel, LaunchDismissLater, LaunchDismissSkip, LaunchReady] |
| 53 | LaunchCheckAgain | LaunchUnknown |  |  | [LaunchDismissIKnow, LaunchDismissCancel, LaunchDismissLater, LaunchDismissSkip, LaunchReady] |
| 460 | DailyGameFlow | GameRewardClaimSkipped | StartApp |  | [GameConfirmUserAgreement, GameEnterByTemplate, GameAcceptAgreement, GameLandingReady, GameRewardPageReady, GameOpenRewardFromShelf, GameBackUntilRewardOrShelf] |
| 777 | GameRewardAfterExit | GameRewardClaimSkipped |  | OCR | [ClaimGameRewardAlreadyDone, ClaimGameRewardRow, GameRewardClaimSkipped] |
| 1657 | AdWaitAfterSkip | AdCloseFallbackLeft |  |  | [AdThirdPartyLoginPage, AdConfirmSkipBrowse, AdBrowseOfferModal, AdSkipBrowseOffer, AdContinueWatching, AdCompleted, AdCountdown, AdScrollDownRepeat, AdWaitAfterSkip] |
| 1673 | AdCountdown | AdCloseFallbackLeft |  | OCR | [AdThirdPartyLoginPage, AdConfirmSkipBrowse, AdSkipBrowseOffer, AdContinueWatching, AdCompleted, AdRewardIssued, AdCountdown, AdCloseAfterNormalCountdown, AdBrowseOfferModal, AdScrollDownRepeat] |
| 1897 | ClaimOneReward | ClaimBackUntilRewardOrShelf | StartApp |  | [ClaimRewardPageReady, ClaimOpenRewardFromShelf, ClaimDismissAddShelf] |
| 1908 | ClaimGameReward | ClaimGameBackUntilRewardOrShelf | StartApp |  | [ClaimGameRewardPageReady, ClaimGameOpenRewardFromShelf, ClaimGameDismissAddShelf] |
| 2037 | ClaimDismissAddShelf | ClaimBackUntilRewardOrShelf | Click | OCR | [ClaimOpenRewardFromShelf, ClaimRewardPageReady] |
| 2500 | AdBrowseOfferModal | AdCloseByBackKey | Click | OCR | [AdCouponPopup, AdClickIKnow, AdCaptchaDetected, AdReturnedAfterClose, AdCloseByBackKey] |

#### 3.1.9 OCR 节点总体情况

- OCR 节点共 **133** 个；全部使用 `expected` 正则，**没有任何节点显式写 `threshold`**，即使用 MaaFramework 默认 OCR 分数阈值，旧工程没有记录该默认值。
- 关键入口/完成/失败判定依赖长正则，例如：`AdReturnStable`（`P(dev):1867-1875`）、`AdRewardPageReady`（`P(dev):1309-1317`）、`AdDailyComplete`（`P(dev):1889-1892`）、`AdClickWatch`（`P(dev):1497-1512`）、`AdVideoCounterVisible`（`P(dev):1514-1535`）、`AdCountdown`（`P(dev):1673-1691`）。
- 这些正则是硬编码的自然语言匹配，QQ 阅读改文案就会失效；新设计应把 `expected`、OCR threshold、ROI 都外置为可配置的页面特征。

### 3.2 Python / 工具层写死值

| 类别 | 文件:行号 | 当前值 | 用途 | 是否可配置 | 新方案建议 |
| --- | --- | --- | --- | --- | --- |
| 路径 | `GUI:39-49` | `CLI_PATH`、`RUNNER_PY`、`RUNNER_SCRIPT`、`SOLVER_SCRIPT`、`AD_LOCATOR_SCRIPT`、`SLIDE_SOLVER_SCRIPT`、`INTERFACE_PATH`、`CONFIG_PATH`、`PIPELINE_PATH`、`GUI_SETTINGS_PATH`、`MAA_LOG_PATH` | 固定项目内路径 | 否（源码常量） | 机器配置 + 启动参数；只保留相对项目路径 |
| 路径 | `GUI:50-53` | `D:/Program Files/Netease/MuMu Player 12/shell/MuMuPlayer.exe`、`MuMuManager.exe`、`adb.exe`、`127.0.0.1:16384` | 模拟器/ADB 位置 | 否 | 机器配置：`emulator.path`、`adb.path`、`device.serial` |
| 路径 | `GUI:64-67` | `G:\project_I\logs\qq_reader_final.png` | 最终奖励截图默认输出 | 仅环境变量 `GAMEFLOW_QQ_REWARD_SCREENSHOT` | 配置项 `output.final_reward_screenshot`；不要写死盘符 |
| 计时/次数 | `GUI:71` | `DIRECT_READING_DWELL_SEGMENT_MINUTES = 15` | 直接阅读分段停留 | 否 | 配置 `reading.dwell_segment_minutes` |
| 计时/次数 | `GUI:138-142` | `FORMAL_MINUTES = 35/35/25` | 阅读/听书/游戏默认分钟 | 部分（GUI 配置可改） | 配置模型 `task.minutes`，保留默认值但可覆盖 |
| 计时/次数 | `GUI:151-158` | `DEFAULT_COUNTS = 2/1/1/1/1/1` | 各任务默认次数 | 部分（GUI 配置可改） | 配置模型 `task.count` |
| 环境 | `GUI:77-78` | `ANDROID_ADB_SERVER_PORT=5038` | MuMu ADB server 端口 | 仅环境变量 | 机器配置 `adb.server_port` |
| 超时 | `GUI:1704-1710` | ADB screencap `timeout=20s` | 保存验证码现场 | 否 | 配置 `timeouts.screenshot` |
| 超时 | `GUI:1726-1734` | 图片 solver `timeout=90s` | 自动点选 | 否 | 配置 `timeouts.captcha_click` |
| 超时 | `GUI:1759-1768` | 广告定位器 `timeout=45s` | 广告卡片定位 | 否 | 配置 `timeouts.ad_locator` |
| 超时 | `GUI:1796-1803` | 滑块 solver `timeout=45s` | 自动滑动 | 否 | 配置 `timeouts.captcha_slide` |
| 重试/节流 | `GUI:1662-1668` | 广告定位：>8s、最多 8 次 | 广告入口失败兜底 | 否 | 配置 `recovery.ad_locator.throttle/attempts` |
| 重试/节流 | `GUI:1678-1685` | 滑块：>8s、最多 6 次 | 滑块启发式触发 | 否 | 配置 `captcha.slide.throttle/attempts`，并由显式状态触发 |
| 失败判定 | `GUI:1628-1646` | `Tasker.Task.Failed`、`Failed to connect controller`、`No available screencap method`、`failed to init screencap` 才 `run_failed=True`；`DirectReadingFlow` 的选择器失败被排除 | GUI 运行失败状态 | 否 | 统一 outcome 模型：SUCCESS/FAILED/TIMEOUT/BLOCKED_BY_CAPTCHA/SKIPPED |
| 路径 | `RUNNER:147-155` | runtime `G:\project_X\dev`、resource `G:\project_X\dev\resource`、adb 路径、`127.0.0.1:16384`、log dir `G:\project_X\dev\debug` | runner 默认值 | 命令行可覆盖，但默认写死 | 全部来自机器配置 |
| 环境 | `RUNNER:95` | `ANDROID_ADB_SERVER_PORT=5038` | ADB server | 否 | 机器配置 |
| 环境 | `RUNNER:101` | `short_side=720` | 分辨率约束 | 否 | 配置 `device.short_side` |
| 路径 | `SUP:32-42` | `ROOT/DEV/LOG/SOLVER/SLIDE_SOLVER/AD_LOCATOR/AD_CLOSE_FINDER/RUNNER/PYTHON/ADB/DEVICE` | supervisor 路径与设备 | 否 | 机器配置 + CLI 参数 |
| 坐标 | `SUP:45-46` | `REFRESH_POINT=(180,908)`、`REFRESH_SETTLE=1.6` | 验证码刷新按钮 | 否 | 配置 `captcha.refresh_point/settle`，优先识别 |
| 重试 | `SUP:59-65` | post-ad 检查间隔 4.0s、等待窗口 10.0s、复查间隔 1.2s、最多 8 次 | 广告结束后延迟验证码 | 否 | 配置 `captcha.post_ad.*` |
| 重试 | `SUP:111` | 图片 solver `for attempt in range(1,31)` | 图片求解总尝试 | 否 | 配置 `captcha.click.max_attempts` |
| 重试 | `SUP:147` | `STALE_CAPTCHA >= 8` 升级 | 连续 stale 帧 | 否 | 配置 `captcha.stale_escalation` |
| 超时 | `SUP:116` | ADB screencap `timeout=15s` | 证据截图 | 否 | 配置 `timeouts.screenshot` |
| 超时 | `SUP:126` | 图片 solver `timeout=120s` | 图片求解 | 否 | 配置 `timeouts.captcha_click` |
| 重试 | `SUP:613-614` | supervisor `max_restarts=8`、`deadline=3*60*60` | 整轮上限 | 函数参数，未从配置读取 | 配置 `supervisor.max_restarts/deadline` |
| 重试 | `SUP:621` | `slide_max_attempts=6` | 滑块尝试上限 | 否 | 配置 `captcha.slide.max_attempts` |
| 重试 | `SUP:628` | `ad_locator_max_attempts=3` | 广告定位尝试 | 否 | 配置 `recovery.ad_locator.max_attempts` |
| 节流 | `SUP:685,695,710` | 8s / 8s / 6s | 图片/滑块/广告定位节流 | 否 | 配置 `recovery.*.throttle` |
| Guard | `GUARD:68-75` | state/evidence/log 路径、默认 adb/device/python/solver | Guard 默认值 | 部分（构造参数） | 机器配置注入 |
| Guard | `GUARD:78-83` | `DEFAULT_MAX_ATTEMPTS=3`、`DEFAULT_VERIFY_ATTEMPTS=4`、`DEFAULT_VERIFY_INTERVAL=1.2`、`DEFAULT_VERIFY_CONSECUTIVE=2` | 求解/验证参数 | 构造参数可覆盖，但默认写死 | 配置 `captcha.max_attempts/verify_*` |
| Guard | `GUARD:157-161, 276-300` | 默认 slide detector/solver 使用 `slide_captcha_solver` | 滑块检测/求解 | 注入 callable | 保持注入，但由 pipeline/状态机统一调用 |
| 滑块检测 | `SLIDE:30-31` | `D:\python\python.exe`、`TARGET_W/H=720/1280` | 外部鼠标/截图工具解释器与分辨率 | 否 | 机器配置 `tools.python`、`device.resolution` |
| 滑块检测 | `SLIDE:49-60` | ADB 截图 `mean<1.0` 视为黑屏 | FLAG_SECURE 兜底 | 否 | 配置 `screencap.black_mean_threshold` |
| 滑块检测 | `SLIDE:147` | 蓝色范围 `(180,50,0)..(255,220,180)` | 找蓝色滑块 | 否 | 特征/模板配置；不要写死颜色 |
| 滑块检测 | `SLIDE:156-159` | 面积 `>=500`、宽 `60..180`、高 `35..100` | 滑块轮廓过滤 | 否 | 配置/模板匹配 |
| 滑块检测 | `SLIDE:165,190,216,226` | 灰色范围 `180..220`、横向长条 `>40%` 宽 | 找灰色轨道 | 否 | 配置/模板匹配 |
| 滑块检测 | `SLIDE:184-185,210-217,224-227` | 轨道搜索带 ±60px、标题下方 10px、全宽 40% | 轨道 ROI | 否 | 配置 `captcha.slide.track_roi` |
| 滑块检测 | `SLIDE:269-274` | puzzle 区域 `track_y-300..track_y-35`、左右 10px | 缺口搜索 ROI | 否 | 配置 `captcha.slide.puzzle_roi` |
| 滑块检测 | `SLIDE:287-293` | 缺口 blob 面积 `500..25000`、宽高 `20..150`、忽略边缘 2px | 缺口过滤 | 否 | 配置/模型 |
| 滑块检测 | `SLIDE:305,308,314,318` | Canny `50/150`、右边缘忽略 60px、平滑核 7、峰值 `<1.0` 放弃 | 边缘投影 fallback | 否 | 配置/模型 |
| 滑块检测 | `SLIDE:343` | 距离 `<=0` 或 `> track_w*1.5` 放弃 | 距离 sanity | 否 | 配置 `captcha.slide.max_distance_ratio` |
| 滑块滑动 | `SLIDE:391-392` | `duration=600ms`、`external=True`、`input_method=emulator` | 滑动参数 | CLI 参数可覆盖，默认写死 | 配置 `captcha.slide.duration/input_method` |
| 滑块滑动 | `SLIDE:416-430` | emu_mouse → maa_click adb → adb shell 三级 fallback | 物理滑动 | 否 | 保留 fallback，但每级都要返回可验证结果 |
| 广告定位 | `LOC:39-65` | HEADER/BUTTON/COUNTER/INVITE 正则 | 广告卡片文本定位 | 否 | 页面特征配置 |
| 广告定位 | `LOC:176,221-227,244-254` | 邀请距离 60px、卡片 margin 20/12、x 范围 520..660、偏移 80/90 | 广告卡片/按钮坐标 | 否 | 优先 OCR target；坐标只做 fallback 配置 |
| 广告定位 | `LOC:274,286` | tap settle 0.6s、adb timeout 30s | 点击/命令超时 | 否 | 配置 `actions.tap_settle`、`timeouts.adb` |
| 图片 solver | `CLICK:188,204` | SIFT `nfeatures=240, contrastThreshold=0.01, edgeThreshold=10`；NMS `iou=0.35` | 图片点选匹配 | 否 | 配置/模型；至少记录版本 |
| 图片 solver | `CLICK:423,626,637,650` | tap timeout 30s、点击间隔 0.45s、连续 2 次 no-op 放弃、提交后等待 2.0s | 点选/提交 | 否 | 配置 `captcha.click.*` |
| 文档漂移 | `docs/CAPTCHA.md:28` | 声称 pipeline 有 `auto_solve_captcha: true` | 文档与实现不符 | N/A | 更新文档；以代码/配置为准 |
| 文档漂移 | `docs/CAPTCHA.md:29` | 声称 `run_ad_with_captcha.py` 自动调用 solver | 对 supervisor 成立，但 GUI 不调用 supervisor | N/A | 明确 GUI/CLI/supervisor 三条路径 |
| 文档缺失 | `docs/GUI.md:28` | 只描述图片点选和广告定位 | 未提滑块 watcher | N/A | 补充滑块/验证码状态说明 |
| 文档缺失 | `docs/TRIAL_PLAN.md:21` | 只写“出现图片点选验证码时自动…” | 未提滑块验证码 | N/A | 补充滑块分支和 CaptchaGuard |

### 3.3 失败条件清单

| 条件 | 位置 | 当前行为 | 问题 |
| --- | --- | --- | --- |
| 单个识别失败 | pipeline 通用 | `Node.Recognition.Failed` 后继续评估 `next` 列表；不自动 = Task Failed | 与 AGENTS.md 3.9 方向一致，但旧工程没有统一 outcome |
| `AdCaptchaDetected` 失败 | `P(dev):1770-1781`；日志 4749 | 继续匹配 `AdReturnStable` / `AdDailyRepeat`，流程继续 | 验证码漏检被静默降级为“没验证码” |
| 无条件 DirectHit 节点 | `AdDailyRepeat` `P(dev):1877-1880`；`AdScrollToVideoCard` `P(dev):1414-1434` | 无 recognition，永远成功 | 识别失败后仍有 fallback 继续滑动/点击 |
| `AdReturnStable` OCR | `P(dev):1867-1875` | 滑块弹窗上方仍能看到奖励页文案时，OCR 命中，流程继续 | 页面状态判定不排他；captcha 不是第一优先级 |
| 广告扫描耗尽 | `AdVideoSearchExhausted` `P(dev):1436-1438` | `DoNothing`，静默结束 | 没有区分“没广告”与“识别失败” |
| 领奖扫描耗尽 | `ClaimGameScanExhausted` `P(dev):2021-2023` | `DoNothing` | 未领取状态可能被当成正常结束 |
| 游戏奖励入口不可用 | `GameRewardEntryUnavailable` `P(dev):475` | 无 next/on_error，安全跳过 | 没有 outcome 记录 |
| 游戏领奖跳过 | `GameRewardClaimSkipped` `P(dev):788` | `DoNothing` | 跳过不等于失败，但也没有结构化结果 |
| 只有显式 StopTask | `AdCaptchaAbort` `P(dev):1850-1852` | 唯一明确停止节点 | 其它验证码/识别失败路径不会停止 |
| 终端节点无 next/on_error | 见 3.3.1 | 节点结束后 pipeline 可能自然结束 | 成功/失败/跳过无法区分 |
| GUI 运行失败 | `GUI:1628-1646` | 只对 `Tasker.Task.Failed`、连接失败、screencap 失败置 `run_failed`；`DirectReadingFlow` 选择器失败明确排除 | 验证码阻塞不会进入失败状态 |
| supervisor 任务失败 | `SUP:680-682` | 只打印 `Maa task reported failure` | 没有把失败转成结构化 outcome |
| 任务级超时 | `assets/interface.json:25-62` | 没有 per-task timeout 字段 | 任务超时只能靠节点级 `timeout`（仅 6 个）或 supervisor deadline |

#### 3.3.1 无 `next` / `on_error` 的终端节点（dev 快照，行号）

| 行号 | 节点 | action | recognition |
| --- | --- | --- | --- |
| 64 | LaunchReady |  | OCR |
| 69 | LaunchUnknown |  |  |
| 84 | SmokeRewardPage |  | OCR |
| 89 | SmokeShelfPage |  | OCR |
| 94 | SmokeReaderPage |  | OCR |
| 99 | SmokeGamePage |  | OCR |
| 104 | SmokeUnknownPage |  |  |
| 120 | ReadingFindBookTerminal | Click | TemplateMatch |
| 136 | ReadingFindBookByTitleTerminal | Click | OCR |
| 151 | ReadingOpenFirstShelfBookTerminal | Click | OCR |
| 300 | ReadingExitAfterTimer | ClickKey |  |
| 448 | AudiobookPauseAfterTrial | Click |  |
| 475 | GameRewardEntryUnavailable |  | OCR |
| 788 | GameRewardClaimSkipped | DoNothing |  |
| 792 | GameShelfAfterExit |  | OCR |
| 864 | ExternalReachedBottom |  | OCR |
| 955 | ExternalBaiduReachedBottom |  | OCR |
| 1013 | ExternalBothComplete |  | OCR |
| 1020 | ExternalBothReturnedComplete |  | OCR |
| 1183 | LevelPointsSectionFound |  | OCR |
| 1188 | LevelAfterPointsAd |  | OCR |
| 1436 | AdVideoSearchExhausted | DoNothing |  |
| 1725 | AdFinish |  |  |
| 1850 | AdCaptchaAbort | StopTask |  |
| 1889 | AdDailyComplete |  | OCR |
| 1991 | ClaimGameRewardAlreadyDone |  | OCR |
| 1996 | ClaimGameRewardClaimed |  | OCR |
| 2021 | ClaimGameScanExhausted | DoNothing |  |
| 2065 | ClaimRewardEntryUnavailable |  | OCR |
| 2144 | ClaimEnabledTextColor |  | ColorMatch |
| 2191 | ClaimReachedBottom |  | OCR |
| 2385 | PlanScanDone |  |  |
| 2487 | FinalEvidenceTopReady |  | OCR |

共 33 个。

### 3.4 新设计配置映射（直接输入给配置模型）

| 旧写死值 | 新配置键（建议） | 说明 |
| --- | --- | --- |
| `max_hit` | `retry.max_attempts` + `retry.reason` | 按页面/动作分别配置，不用统一 retry N → false |
| `post_delay` | `waits.after_action_ms` / `state_settle_ms` | 页面加载等待外置；按状态/动作配置 |
| `threshold` | `recognition.template_threshold` | 每个模板单独阈值；记录实际 score |
| OCR `expected` | `recognition.ocr_patterns` + `recognition.ocr_threshold` | 正则与阈值都外置；旧工程 133 个 OCR 节点没有 threshold |
| `roi` | `recognition.roi` | 按页面/特征配置；滑块轨道/缺口 ROI 单独配置 |
| `target` / `begin` / `end` | `actions.coordinates`（仅 fallback） | 优先识别目标；固定坐标必须标注为 fallback 并可配置 |
| `timeout` | `timeouts.step` / `timeouts.task` | 节点级 + 任务级独立超时；区分 TIMEOUT 与 FAILED |
| GUI 8s/6 次、SUP 8s/6 次 | `captcha.slide.throttle_ms` / `captcha.slide.max_attempts` | 由显式 `CAPTCHA_DETECTED` 状态触发，而不是广告按钮失败启发式 |
| `GUARD` 4/1.2/2 | `captcha.verify_attempts/interval/consecutive` | 保留“连续 N 帧 NONE 才算消失”的验证契约 |
| 硬编码路径 | 机器配置 `emulator.path` / `adb.path` / `device.serial` / `tools.python` | 不写盘符、用户名、项目绝对路径 |
| `StopTask` / `on_error` | `failure_policy` + `outcome` | 每个任务显式定义 success_condition / failure_condition / captcha_condition |

## 4. 待实机确认

1. 在当前 QQ 阅读版本重新截图制作 `qq_reader_captcha_prompt.png`（图片点选）和滑块验证码模板/特征，测量实际匹配分数，重新标定 threshold/ROI。
2. 在真机/模拟器上确认滑块页面当前的颜色、轨道、缺口布局，验证 `slide_captcha_solver.detect` 是否仍能 `found=true`。
3. 确认图片点选验证码在当前版本是否还会出现；旧日志 0 次成功，不能假定模板仍有效。
4. 确认 Maa/ADB screencap 在验证码页、广告页、FLAG_SECURE 正文页的实际行为；验证 `mean<1.0/10.0` 阈值是否合适。
5. 确认求解后验证的截图时机、连续帧数、刷新行为；当前滑块主路径没有验证。
6. 确认 `CaptchaGuard` 如何接入 pipeline/GUI：V1 目标是“任何关键操作前检测 → CAPTCHA_DETECTED 阻塞 → solver → verify_cleared → 恢复”，而不是 GUI watcher 的事后启发式。

## 5. 证据索引

- 验证码调用链：`GUI:41-44, 641-655, 1603-1694, 1699-1824`；`RUNNER:117-119`；`SUP:29, 197-228, 346-362, 613-707`；`GUARD:157-161, 189-230, 233-269, 276-300, 479-538, 575-597`。
- 模板/阈值/ROI：`P(dev):1770-1781, 1783-1799, 1839-1852`；`assets/resource/image/qq_reader_captcha_prompt.png`。
- 真实日志：`G:\project_X\dev\debug\maafw.bak.2026.09.07-14.28.25.187.log` 4676、4747-4758、4786-4800、4880-4906、5094-5098。
- 滑块证据截图：`G:\project_X\dev\debug\slide_evidence_20260907_142107.png`（OCR `安全验证` / `拖动下方滑块完成拼图`）。
- 文档：`docs/CAPTCHA.md`、`docs/GUI.md`、`docs/TRIAL_PLAN.md`。

> 本报告只做静态审计；未修改 `G:\project_X`，未运行真实设备任务。
