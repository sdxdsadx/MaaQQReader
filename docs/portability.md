# 可移植性：不同模拟器与分辨率

本页说明 QQReader 在不同模拟器、不同分辨率下能否使用，以及 2026-10-28 的实测结果。

## 坐标是怎么来的

- 所有任务的坐标和识别区域（ROI）都按 **720×1280、240 DPI** 的竖屏画面标定。这个参考值读自日常使用的 MuMu 12 实例 0（`wm size` 720x1280，`wm density` 240）。
- MaaFramework 会把截图缩放到短边 720（`maa_short_side: 720`），点击时再按比例换算回设备像素。所以只要画面是 **9:16 竖屏**，并且 **DPI 与分辨率等比**，识别和点击就都能用。
- 不经过 MaaFramework、直接 `adb shell input` 的代码要自己换算坐标。目前只有阅读脚本 `scripts/auto_read_30min.py` 这样点击，它已经按 `设备短边 / 720` 换算。

## 分辨率支持表

| 分辨率 / DPI | 结论 | 说明 |
| --- | --- | --- |
| 720×1280 / 240 | ✅ 推荐 | 与标定画面一致 |
| 1080×1920 / 360 | ⚠ 可用 | 识别、点击、阅读、广告、游戏都按比例换算；**滑块验证码自动拖动按 720×1280 像素写坐标，可能失败**（验证码模块禁止改动，见 AGENTS.md） |
| 1440×2560 / 480 | ⚠ 可用 | 同上 |
| 720×1280 / 320（雷电 9 新建实例的默认值） | ❌ 拒绝 | 逻辑宽度 360dp，App 版式与标定画面不同 |
| 1080×1920 / 240 | ❌ 拒绝 | 9:16，但 DPI 没跟着改 |
| 1080×2400 等 20:9 | ❌ 拒绝 | 缩放后高 1600，纵向坐标错位 |
| 任何横屏（1920×1080、1280×720） | ❌ 拒绝 | QQ 阅读是竖屏应用 |

DPI 的算法：`DPI = 设备短边 × 240 / 720`，例如 1080 宽配 360、1440 宽配 480。

连接设备时会自动检查（`qqreader/maa/display.py`）：

- ✅ 不提示；⚠ 打印一行提示后继续；❌ 拒绝连接，并告诉你改成什么分辨率 / DPI。
- 确实要在不兼容的画面上试跑，可设环境变量 `QQREADER_DISPLAY_CHECK=warn`（只提示）或 `off`（不检查）。
- `调试QQReader.cmd` 的环境体检（`python -m qqreader.maa doctor`）会显示「设备分辨率」和「截图坐标系」两项。

## 模拟器支持表

`启动QQReaderGUI.cmd` 调用 `python -m qqreader.maa.emulator prepare --launch`：从本机配置、注册表和各盘符的默认安装目录找模拟器（没有偏好时 MuMu 优先），读管理工具拿到真实 ADB 端口，必要时拉起模拟器，等 Android 启动完成，检查分辨率，再把 `adb_path` / `adb_address` / `emulator_path` 写回 `configs/qqreader.local.json`。没有本机配置时按示例生成一份。

| 模拟器 | 找安装目录 | 找端口 | 自动拉起 | 实测 |
| --- | --- | --- | --- | --- |
| MuMu 12（`shell\` 与 4.x 的 `nx_main\` 两种目录） | 配置 / 注册表 / 默认目录 | `MuMuManager info -v all` 的 `adb_port`；默认 16384+32·n、7555 | ✅ `MuMuManager control -v N launch` | ✅ 全流程 |
| 雷电 9 | 配置 / 注册表 / 默认目录 | `ldconsole list2`，端口 5555+2·n | ✅ `ldconsole launch --index N` | ✅ 发现、拉起、连接、截图、OCR、分辨率检查（未装 QQ 阅读，见下） |
| BlueStacks 5 | 注册表 `BlueStacks_nxt` | `bluestacks.conf` 的 `adb_port`；默认 5555+10·n | ❌ 请手动启动 | 只由单元测试覆盖 |
| 夜神 | 注册表 | 默认 62001、62025+n | ❌ 请手动启动 | 只由单元测试覆盖 |
| 逍遥 | 注册表 | 默认 21503+10·n | ✅ `memuc start -i N` | 只由单元测试覆盖 |
| 真机 / 其他 | PATH 里的 `adb` | `adb devices` 已在线的设备 | — | 只由单元测试覆盖 |

- 多开时用 `set QQREADER_EMULATOR_INDEX=N` 指定实例序号（默认 0），再运行启动脚本。
- 只想看会选中哪个设备、不改配置：`py -3.10 -m qqreader.maa.emulator detect --config configs\qqreader.local.json`。
- 每个模拟器用自己目录里的 adb；不同版本的 adb 混用会互相重启 adb 服务。

## 换到新模拟器 / 新电脑的步骤

1. 在模拟器里把分辨率设成 **720×1280、DPI 240**（手机版 / 竖屏）。雷电 9 新建实例默认是 320 DPI，要手动改。
2. 在模拟器里安装 QQ 阅读并登录（登录要你自己完成）。
3. 双击 `启动QQReaderGUI.cmd`。它会找到模拟器、写好本机配置。看输出里的「分辨率检查」一行是不是 `[ok]`。
4. 选预设「1 分钟试跑」跑一次。

## 2026-10-28 实测记录

都用本分支的代码、命令行运行，不经 GUI。

| 环境 | 体检 | 任务 | 结果 |
| --- | --- | --- | --- |
| MuMu 12 实例 0，720×1280 / 240 | 通过 | `LaunchQQReader`；`DailyReadingFlow --minutes 1` | 均 exit 0；正文停留 1 分钟，阅读奖励已领 |
| 同上，`wm size 1080x1920` + `wm density 360` | 通过（⚠ 提示滑块） | `DailyReadingFlow --minutes 1` | **修复前 exit 3**：书名点击没换算，点中了上一行「我的笔记」；修复后 exit 0 |
| 1080×1920 / 360 与 720×1280 / 240 各一次 | — | `DailyGameFlow --duration-minutes 1` | 两次都 TIMEOUT，且过程完全相同：奖励页滚到底也没有「玩游戏 / 在线时长」任务行（当天页面没有这一行）。与分辨率无关 |
| MuMu，`wm density 320`（720×1280） | 连接被拒绝，提示改 DPI 240 | `LaunchQQReader` | exit 12（设备错误），符合预期 |
| 雷电 9 实例 2，720×1280 / 320（新建实例默认值） | 严格模式拒绝；`QQREADER_DISPLAY_CHECK=warn` 下连接、截图、OCR、点击通过 | 未跑：该实例没装 QQ 阅读 | `prepare --launch` 28 秒拉起并连上 127.0.0.1:5559；`wm density 240` 后判定变为 ok |
| 全新机器（没有本机配置、没有任何路径提示） | — | `prepare --launch --example …` | 从注册表找到雷电，生成配置并填好 adb |

测试结束后 MuMu 已执行 `wm size reset`、`wm density reset`，雷电已 `wm density reset`，两台模拟器都关回测试前的状态。
