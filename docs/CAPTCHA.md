# 验证码检测模块

项目在 `.venv-captcha` 中部署了 `ddddocr 1.5.6`。该模块首先用于离线检测验证码截图中“请在下图依次点击”的顶部灰色提示图标与彩色候选图，并用 OpenCV 做二值化/骨架匹配 + SIFT 特征匹配，按顶部提示的顺序从左右依次给每个提示选一个候选图，再点选并提交。

使用方法（单独查看/标注某张截图，不点选、不提交）：

```powershell
G:\project_X\.venv-captcha\Scripts\python.exe G:\project_X\tools\captcha_inspect.py 截图.png
```

自动求解与点选（`--submit` 为默认行为：按顺序点选候选图、点蓝色提交按钮、检测是否仍停留）：

```powershell
G:\project_X\.venv-captcha\Scripts\python.exe G:\project_X\tools\captcha_solver.py `
  --adb "D:\Program Files\Netease\MuMu Player 12\shell\adb.exe" `
  --device 127.0.0.1:16384 --submit --click-engine maa
```

`--click-engine` 可选 `maa`（默认，通过本地 MaaFramework 的 `MaaControllerPostClick` 下发坐标点击，与 Maa 走同一条 ADB 输入通道）或 `adb`（`adb shell input tap`，作为兜底）。点选结果默认写回 MAA，验证通过后 MAA 会检测到奖励页继续自动执行。

## 自动点选策略（2026-08-20 起调整）

实机测试已经证明“顺序点选方案可行”：按顶部灰色提示图标顺序，在图片中匹配对应彩色图形并依次点击，提交后显示“奖品已发放”，视频次数由 `2/12` 增至 `3/12`。通过一次验证码后，同一会话内后续多次广告不再出现验证码并顺利到 `12/12`。

因此正式流程从“保留验证码等人工”调整为**自动顺序点选并提交**：

1. `captcha_solver.py --submit` 负责识别、按序点选、提交并核验是否成功。
2. GameFlow 的 `qq_reader_trial` 工作流在 MAA 日志出现 `AdCaptchaDetected` 时，自动拉起求解器（`auto_solve_captcha: true`），点选成功后 MAA 自动续跑。
3. 独立脚本 `run_ad_with_captcha.py` 同样自动调用求解器并提交。

说明与边界：

- 验证码属于反自动化验证，不同会话/日期可能再次出现；本方案只在它实际出现后触发，未出现时不影响广告流程。
- 求解器在差异过小或布局异常时会拒绝点选（`captcha_layout:false` 或抛错），不会盲目乱点；此时保留当前页面，可人工完成。
- “已经返回奖励页”不能当作广告成功——成功仍以“奖品已发放”、视频次数增加或 `12/12`/“明日再来”为准。
- 选择 1.5.6 是因为 1.6.0 的 Windows wheel 存在包内同名模块冲突，无法正常导入 `DdddOcr`；1.5.6 已通过导入和模型初始化测试。

