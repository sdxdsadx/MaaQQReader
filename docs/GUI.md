# 可视化界面

## 直接使用

双击项目根目录的 `MaaQQReaderGUI.exe`，也可以双击 `启动可视化界面.cmd`。

界面支持：

- 一键启动 MuMu 模拟器，并等待 `127.0.0.1:16384` 设备上线
- 一键启动 QQ 阅读，通过 MAA 关闭“我知道了”“取消”“稍后再说”“跳过”等已知安全弹窗
- 检查 MuMu 模拟器连接状态
- 勾选需要执行的任务，并通过上移、下移调整串行运行顺序
- 分别设置自动阅读、听书、游戏的单次运行分钟数
- 设置每项任务的重复次数；阅读、听书和游戏最多 99 次，奖励页广告、等级页广告及外部应用完整流程固定为 1 次。重复次数大于 1 时，开始前会显示展开后的任务总数并要求确认
- 使用“1分钟×1”快速切换为短时测试，或使用“每日默认配置”恢复自动阅读 2 次×35 分钟、听书 35 分钟、游戏 25 分钟
- 停止正在执行的任务
- 查看 MaaPiCli 实时输出
- 在独立命令行窗口打开原始 CLI

界面的编排设置保存在 `dev/config/maa_gui_config.json`，可以直接修改每项的 `minutes` 和 `count`。启动任务时会临时更新 `dev/config/maa_pi_config.json` 和流水线中的计时值，进程结束或停止后恢复运行前的原始内容，因此 `MaaPiCli.exe` 的交互式使用方式保持不变。默认 CLI 编排在 `dev/config/maa_pi_config.json` 中保存为两条自动阅读、一条听书、一条游戏、一条外部应用流程和一条等级页广告流程；需要修改 CLI 固定次数时增删对应任务条目即可。

“外部应用每日流程”仅打开已安装的大众点评和百度地图，然后返回 QQ 阅读核对“明日再来”。京东金融已从该流程移除；脚本不会下载应用，也不会执行登录、签到、提现或其他应用内操作。

“等级页广告每日流程”从“我的 → 等级”进入，依次处理赠币广告和积分广告。它复用奖励页广告的普通倒计时、直播下滑、关闭及验证码处理；第三方登录授权页会立即返回，不会代替用户登录或授权。

“启动 QQ 阅读”不会自动同意系统权限、点击广告详情或执行升级安装；遇到不认识的弹窗时只记录日志并停止自动点击。

广告结束后若出现图片点选验证码，脚本会自动按顶部灰色提示的顺序点选彩色候选并提交（`tools/captcha_solver.py --submit`）；若 `AdClickWatch`/`AdVideoCounterVisible` 找不到“立即观看”，会使用 `tools/ad_locator.py` 从 Maa 日志重建广告卡片并定位观看按钮后点击。界面同时读取 MaaFramework 的任务结果，底层失败时不再误报为执行成功。

“领取全部已完成奖励”会先回到奖励页顶部，再逐页向下扫描，仅点击金色可用的“领取/立即领取”按钮，直到页面底部。

## 命令行模式

在 `dev` 目录执行：

```powershell
.\MaaPiCli.exe
```

也可以点击界面右上角的“打开 CLI”。

## 从源码启动或重新打包

源码启动：

```powershell
python .\gui\maa_qq_reader_gui.py
```

重新生成单文件程序：

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name MaaQQReaderGUI .\gui\maa_qq_reader_gui.py
Copy-Item .\dist\MaaQQReaderGUI.exe .\MaaQQReaderGUI.exe -Force
```
