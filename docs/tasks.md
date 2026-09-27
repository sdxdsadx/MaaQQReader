# 任务与运行机制

每个自动化任务做什么、默认参数，以及 ADB 预检、广告、验证码等运行细节。

> 返回 [README](../README.md)

## 任务一览

| 任务 key | 名称 | 默认参数 | 今日流程 |
| --- | --- | --- | --- |
| `LaunchQQReader` | 启动 QQ 阅读并关闭开屏弹窗 | — | 工具按钮 |
| `SmokeTest` | 页面识别检查 | — | 工具按钮 |
| `DailyReadingFlow` | 每日自动阅读，结束后自动领取阅读奖励 | 2 次 × 35 分钟，超时 50 | ✓ |
| `DailyAudiobookFlow` | 每日听书，结束后关闭悬浮框并领取赠币 | 35 分钟，超时 50 | ✓ |
| `DailyGameFlow` | 奖励页 → 去玩游戏 → 游戏大厅 → 在线玩 → 游戏中心 → 登录/协议 → 领币计时 → 退出 | 挂机 25 分钟，超时 35 | ✓ |
| `DailyAdFlow` | 奖励页视频广告，目标 12/12 | 超时 45 | ✓ |
| `DailyLevelAdFlow` | 我的 → 等级：赠币广告 + 积分广告 | 超时 30 | ✓ |
| `DailyExternalAppFlow` | 外部应用（大众点评 + 百度地图） | 超时 30 | 可选 |
| `ClaimOneReward` | 重新检查阅读奖励（失败重试用） | 超时 10 | 可选 |
| `ClaimAudiobookReward` | 仅领取已达标的听书奖励 | 超时 10 | 可选 |

任务目录定义在 `qqreader/gui/task_catalog.py`，新增任务只需在 `DEFAULT_TASK_CATALOG` 中登记，GUI 会自动生成队列行与参数表单。

## 运行机制要点

### ADB / 截图预检

`qqreader/maa/adb.py` 在 MAA 连接前执行：

1. `adb connect`，并等待 `sys.boot_completed=1`；
2. 试执行 `adb exec-out screencap -p`；
3. 截图为空时（阅读页 `ReaderPageActivity` 设置了 FLAG_SECURE，禁止截屏），自动 `am force-stop` 并重新启动 QQ 阅读。

任务运行中如果 MAA `screencap` 返回 4000（误入阅读页），`CtypesMaaClient.screencap` 会同样退出并重启，最多重试 3 次。这样可以避免反复出现 `No available screencap method`。

### 广告

- 进入 `AD_PLAYING` 后先等待 **40 秒**，再处理跳过 / 继续观看 / 退出确认；每轮广告单独计时。
- 直播或浏览类广告（`进入直播间` / `直播中` / `上滑或点击` 等）改为每 **5 秒下滑一次**，默认 8 次后退出。
- 遇到「我要加速 / 去加速 / 加速观看」时先点击，以便继续观看；遇到奖励完成弹窗时点左上角关闭。
- 奖励页必须识别到广告卡标题 `看小视频领好礼` 才去定位观看按钮。按钮被遮挡时先滑动移开卡片，不补点固定坐标。按钮坐标只在当前帧内有效。

### 滑动验证码

- `PageState.CAPTCHA` 通过 OCR 识别 `安全验证` / `拖动下方滑块完成拼图`，优先级高于普通页面识别；
- `SlideCaptchaSolver` 用 OpenCV 定位滑块、轨道和缺口，再执行滑动；
- `VerifyingCaptchaGuard` 求解后必须重新观测，确认验证码消失后才恢复任务；
- 多次尝试仍失败时返回 `BLOCKED_BY_CAPTCHA` / `WAITING_FOR_HUMAN`，不再继续点击。
