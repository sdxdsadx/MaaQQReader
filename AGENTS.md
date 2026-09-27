# AGENTS.md

QQReader：Windows 本地运行的 QQ 阅读每日任务自动化（MaaFramework + MuMu 模拟器 + ADB）。
需求、架构、验收标准和排障记录在 [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md)；最近改动在 [`CHANGELOG.md`](CHANGELOG.md)。
**开工前先读 CHANGELOG 最上方 3 条。**

## Project overview

- 唯一维护目录：`G:\project_X`。`Documents\Codex` 下的旧脚本已归档到 `docs/legacy/`，不要运行旧入口。
- 旧工程 `_backup_old_project_20260909_200716/` 只作参考，不在其中修改；但它**仍是运行依赖**：听书任务 `DailyAudiobookFlow` 目前通过其中的 `tools\run_maa_ad.py` 调用旧流程（2026-09-27 试跑日志确认），不要移动、重命名或删除它。
- 代码入口：
  - `qqreader/`：核心包（页面状态机、任务契约、恢复、验证码守卫）
  - `qqreader/maa/`：MaaFramework 适配
  - `qqreader/tasks/ad.py`：广告任务
  - `qqreader/gui/`：GUI
  - `scripts/run_task.py`：命令行单任务入口，含 pipeline 运行时覆盖
  - `tests/`：单元测试
- 本机数据：配置在 `configs/qqreader.local.json`；任务次序和次数在 `runtime/gui_tasks.json`；日志和截图在 `runtime/`。
- Linear 项目 MAAQQReader，Issue 编号 `QQR-xx`。

## Dev environment

- Python 3.10：用 `py -3.10`。不要改全局环境，不要随意加依赖；需要新依赖时先问用户。
- 模拟器：MuMu 12 实例 0，ADB `127.0.0.1:16384`，分辨率 720×1280，包名 `com.qq.reader`。端口以本机配置和运行时为准，不写死。
- 根目录只保留两个启动脚本，不要新增 bat/cmd：
  - `启动QQReaderGUI.cmd`：日常使用
  - `调试QQReader.cmd`：冷启动、体检、识别检查、单任务、测试、冷停止
- `调试QQReader.cmd` 必须保持 **GBK** 编码，调用外部程序后要重新执行 `chcp 936`。其余源码和配置一律 UTF-8。
- 启动 GUI 必须用 `启动QQReaderGUI.cmd`（它会定位 Python、查询 MuMu 的 ADB 端口、写入本机配置、设置 PYTHONPATH）。直接双击 `dist\QQReaderGUI.exe` 不会加载本机配置，运行时会提示“请先加载本机配置文件”。
- 打包 GUI：`scripts\build-gui-exe.cmd`，产物为 `dist/QQReaderGUI.exe`。GUI 会加载当前源码，改了源码不一定要重新打包；改了 GUI 本身才需要重建。

## Testing instructions

- 全部测试：`py -3.10 -m pytest`。改动哪块就先跑对应测试文件，提交前再跑全量。
- 冒烟试跑（实机，约 7 分钟）：GUI 侧栏「选择1分钟试跑」（每日自动阅读 → 每日游戏 → 每日听书，各 1 分钟）→「直接运行已选」。三项都应显示“成功”，汇总记录在 `runtime/records/daily_flows/`。改动任务流程后、推送前跑一次。
- 只改文档（`*.md`）时可以不跑测试，但要在交付里说明“未跑测试，原因：仅文档”。
- 缺陷修复要补回归测试。识别相关的测试用真实截图和真实 OCR，不要只在伪造模板或假对象上通过。
- 实机验证用 GUI：点「全不选」，只勾选要验证的任务，再点「直接运行已选」或「单独运行此任务」。已经验证成功的任务不要重复跑。
- 如实报告结果：中断、超时、被验证码阻塞都要写出来。实机没有触发到的分支，标成"只由单元测试覆盖"。
- 不要为了让测试通过而删除断言、跳过测试或伪造数据。

## Domain rules (do not break)

- 识别不到目标 ≠ 任务失败：先重新截图，确认页面、弹窗和验证码，再按恢复阶梯处理；不要连续几次 `Match False` 就退出。
- 页面状态是 `UNKNOWN` 时，不点击，也不判失败。
- 关键点击必须按"识别 → 点击 → 验证页面变化"来做，不能点完就默认成功。
- 检测到验证码时，不走普通恢复：不返回、不重启 App、不继续点击。状态记为 `BLOCKED_BY_CAPTCHA` / `WAITING_FOR_HUMAN`；求解后必须确认验证码已经消失。求解器改动归 QQR-34。
- 任务从公共起点自己进入入口，例如广告任务从主页进入奖励页。
- 成功只认该任务的 `success_condition`。例如广告必须看到广告卡 `12/12` 或该卡的"明日再来"；"已返回奖励页""没报错"都不算。
- 不要为修复单个任务而改 Gameflow 调度核心或备份目录。

## CHANGELOG

每次改动（代码、pipeline 覆盖、启动脚本、GUI 行为、配置默认值、Git 规则）都要在 `CHANGELOG.md` **最上方**加一条，按文件开头的模板写：

触发来源 → 现象 → 根因 → 修改（写到文件、函数或节点名）→ 验证（测试数、实机运行 ID）→ 未覆盖 / 遗留 → 分支 → 回滚方式。

CHANGELOG 条目和对应代码放在同一个提交里。

## Git & GitHub

- 远端：**`github`** → `https://github.com/sdxdsadx/MaaQQReader.git`（没有 `origin`）。主分支是 `master`。
- 不要直接在 `master` 上提交。每个任务或 Issue 开一个分支，命名为 `<agent>/<主题>-<YYYYMMDD>`，例如 `codex/qqr-33-ad-fix-20260927`。分支的上游必须是**同名**远端分支，不能是 `github/master`。
- 开工前先看 `git status --short`。如果有不属于本任务的改动，不要提交、不要 stash、不要还原，先告诉用户。
- 暂存时逐个 `git add <文件>`，然后用 `git diff --cached --stat` 检查。禁止 `git add -A` 或 `git add .`。
- 提交信息格式：`<type>(QQR-xx): <中文摘要>`。type 取 `feat` `fix` `test` `docs` `refactor` `build` `chore` 之一。正文写原因和验证结果。一个提交只做一件事。
- 测试通过后，可以在任务分支上直接做本地提交。
- 以下操作都要先得到用户在对话里的明确同意：推送（`git push -u github <分支>`）、合并到 `master`（`--no-ff`，合并后重跑测试）、推送 `master`、打标签或发 Release。
- 推送前的自查：
  - 查看将上传的提交：`git log --oneline github/master..HEAD`
  - diff 中没有 token、password、cookie、api key
  - 没有超过 5 MB 的文件
  - 测试已通过，CHANGELOG 已更新
- 回滚用 `git revert <hash>`；合并提交用 `git revert -m 1 <hash>`。定位提交：`git log --oneline -S "<CHANGELOG 条目标题>" -- CHANGELOG.md`。
- 高风险操作前先建保护点：`git branch backup/<YYYYMMDD>-<原因>`。实机验收通过的版本打标签：`git tag -a verified/<YYYYMMDD>-<任务>`。
- 用 Git 做备份，不再创建 `*.bak` 文件，也不再复制整个项目目录。
- 禁止以下操作：`push --force`；改写已推送的历史；`--no-verify`；未经用户同意执行 `reset --hard`、`clean`、`stash drop`，或删除分支和标签；修改全局 git config 或凭据。
- 遇到合并冲突或推送失败时停下，把情况报告给用户，不要自行绕过。

## Security & data

- 以下内容不进仓库，也不上传 GitHub：
  - `runtime/`（截图可能包含账号信息）
  - `configs/*.local.json`
  - `build/`、`dist/`、`*.exe`
  - `_backup_*/`、`*.bak*`（注意：因此从 GitHub 克隆的仓库缺少听书任务依赖的旧流程脚本，换机时需要单独拷贝该目录）
  - `.hermes/`、`.serena/`
  - 任何密钥、token、cookie
  - 如果发现这些内容已经被跟踪或已经推送，停下报告，不要自己改写历史。
- 示例配置里只放占位值。不在源码中写死盘符、用户名或绝对路径。
- 禁止在 App 里执行以下操作：充值、购买、邀请、分享、提交个人信息、第三方授权登录。
- 停止单次运行时，不要按进程名批量结束进程。

## Done checklist

交付时逐项报告：

1. 改了哪些文件
2. 测试结果（测试数、失败项）
3. 实机结果或"未实机验证"
4. CHANGELOG 条目标题
5. 分支名和提交 hash
6. 是否已推送、是否已合并
7. 遗留问题

没有执行过的命令，不能写成"已验证"。
