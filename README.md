# Codex Reset Pet · 桌面重置小精灵

[![简体中文](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-0969da?style=for-the-badge)](README.md)
[![English](https://img.shields.io/badge/Language-English-6e7781?style=for-the-badge)](README.en.md)

由于本人经常忘记重置的节点，导致很多重置都浪费了。然后搞了一个这个桌面插件。内置了tibo reset按钮(https://codex-reset.com/zh/tibo)，点击打开即可。

Windows 桌面常驻小精灵，显示 **Codex 账户额度重置** 与 **重置卡到期** 的北京时间、剩余时长，并提供 Tibo 消息查询插件。

<img src="docs/pet-preview.png" width="288" alt="睡眠状态渲染预览，头顶冒出逐渐变大的 zzz">

这是独立的本机桌面程序和 Codex 技能插件，不是 OpenAI 官方 Pets。支持 Windows 10/11；桌面程序无需 API Key。账户同步需要已登录、可提供账户状态工具的 Codex 桌面端。

## 通过 Codex 安装（优先入口）

在 PowerShell 或 Codex 的终端中执行：

```powershell
codex plugin marketplace add FantasyWorld-G/codex-reset-pet --ref v0.4.3
codex plugin add reset-reminder@codex-reset-pet
codex plugin list --marketplace codex-reset-pet
```

安装后新建 Codex 聊天即可使用查询和提醒插件。**这组命令只安装 Codex 插件，不安装 Python/Pillow，也不会启动桌面宠物。** 需要桌面上的剩余额度窗口和刷新按钮时，再执行下方桌面安装；桌面安装器也会注册配套插件。

命令依据 [OpenAI 官方 CLI 文档](https://learn.chatgpt.com/docs/cli/reference)。

## 桌面宠物一键安装

在 **PowerShell** 中复制运行下面这一行（固定安装 v0.4.3）：

**v0.4.3 已包含剩余额度百分比、进度条、刷新按钮、倒计时颜色修复及异常处理修复。** 旧 v0.4.2 安装包没有这些后续功能；已安装用户请执行下方更新命令。

```powershell
$f = Join-Path $env:TEMP 'codex-reset-pet-install.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/v0.4.3/install.ps1' -OutFile $f; powershell -NoProfile -ExecutionPolicy Bypass -File $f
```

安装脚本会下载发布包并核对 SHA-256，检测 Python，必要时通过 winget 安装当前用户的 Python 3.12，在独立虚拟环境安装 Pillow，创建桌面快捷方式，然后启动小精灵。检测到 Codex CLI 时，也会安装配套插件。无需 Git；通常无需管理员权限。首次运行需要连接 GitHub、PyPI；缺少 Python 时还需要 winget 软件源。

安装位置：`%LOCALAPPDATA%\CodexResetPet`。不会自动建立定时任务或开机自启，也不会读取你的登录凭证。可先查看 [安装脚本](install.ps1)，或从 [Release](https://github.com/FantasyWorld-G/codex-reset-pet/releases/tag/v0.4.3) 手动下载。

## 其他安装方式

### 手动下载发布包（无需 Git）

从 [v0.4.3 Release](https://github.com/FantasyWorld-G/codex-reset-pet/releases/tag/v0.4.3) 下载 `codex-reset-pet-v0.4.3.zip` 和 `SHA256SUMS.txt`。将两者放在同一目录，运行下面的校验命令；仅在校验通过后解压，并在解压后的 `codex-reset-pet` 目录运行安装器。

```powershell
$archive = (Resolve-Path '.\codex-reset-pet-v0.4.3.zip').Path
$expected = ((Get-Content '.\SHA256SUMS.txt' | Where-Object { $_ -match '\s+codex-reset-pet-v0\.4\.3\.zip$' }) -split '\s+')[0]
$sha256 = [Security.Cryptography.SHA256]::Create()
$archiveStream = [IO.File]::OpenRead($archive)
try { $actual = ([BitConverter]::ToString($sha256.ComputeHash($archiveStream))).Replace('-','') }
finally { $archiveStream.Dispose(); $sha256.Dispose() }
if ($actual -ne $expected) { throw 'SHA-256 mismatch' }
```

在解压后的目录中：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath .
```

### Git / 源码安装

需要已安装 Git。在准备保存源码的目录运行：

```powershell
git clone --branch v0.4.3 --depth 1 https://github.com/FantasyWorld-G/codex-reset-pet.git
Set-Location codex-reset-pet
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath .
```

也可从 GitHub 下载源码 ZIP，解压后运行同一条 `install.ps1 -SourcePath .` 命令。安装器仍会检查 Python 和安装 Pillow，需要相应网络连接。

### 仅安装桌面程序 / 自定义目录

以下为解压后的发布包或源码目录中的替代命令，按需选择一条：

```powershell
# 仅安装桌面程序，跳过 Codex 插件注册
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath . -SkipPlugin

# 安装到指定目录
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath . -InstallRoot 'D:\Apps\CodexResetPet'

# 安装但暂不启动，也不创建桌面快捷方式
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath . -NoLaunch -NoShortcut
```

仅安装桌面程序仍需已登录的 Codex CLI 才能使用额度刷新。完整参数见 [使用说明](docs/使用说明.md)。

## 一键更新（已安装用户）

先右键人物，选择“退出桌面小精灵”，再在 **PowerShell** 运行：

```powershell
$f = Join-Path $env:TEMP 'codex-reset-pet-update.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/main/update.ps1' -OutFile $f; powershell -NoProfile -ExecutionPolicy Bypass -File $f
```

更新器会查询 GitHub 最新稳定版，下载对应版本的安装器；安装器校验发布包 SHA-256，更新程序、插件及快捷方式，最后启动新版。保留 `data/` 中的账户快照、窗口位置和设置，不创建定时任务。更新失败时按提示处理后重试。

自定义安装目录的用户，在最后的命令末尾添加 `-InstallRoot 'D:\Apps\CodexResetPet'`，路径必须和原安装位置一致。仅安装桌面程序时可加 `-SkipPlugin`；暂不启动可加 `-NoLaunch`，不创建快捷方式可加 `-NoShortcut`。从源码目录直接运行的用户，应更新源码，或用 `install.ps1 -SourcePath .` 安装；本更新器面向安装器管理的目录。

更新后展开气泡，应能看到“剩余额度”和“刷新”按钮。旧聊天可能仍使用插件缓存，插件更新后请开启新聊天。

### 仅更新 Codex 插件

适用于按上方命令添加的 Git 市场。将固定版本切换到 v0.4.3：

```powershell
codex plugin marketplace remove codex-reset-pet
codex plugin marketplace add FantasyWorld-G/codex-reset-pet --ref v0.4.3
codex plugin add reset-reminder@codex-reset-pet
```

以后升级时将 `v0.4.3` 替换为已发布的新标签。若你的 Git 市场明确跟踪 `main`，可改用下面两条；固定标签执行 `upgrade` 不会自动跳到新版本：

```powershell
codex plugin marketplace upgrade codex-reset-pet
codex plugin add reset-reminder@codex-reset-pet
```

如果由桌面安装器注册的是本地市场，请使用前面的桌面更新命令。仅更新插件不会升级桌面文件；完成后新建 Codex 聊天。[官方市场命令说明](https://learn.chatgpt.com/docs/cli/reference)。

## 再次启动与检查版本

双击桌面快捷方式即可。也可读取安装记录启动，不需要写死版本目录：

```powershell
$petRoot = Join-Path $env:LOCALAPPDATA 'CodexResetPet'
$installed = Get-Content -Raw -LiteralPath (Join-Path $petRoot 'install.json') | ConvertFrom-Json
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $installed.appRoot 'start.ps1') -DataDir $installed.dataDir -PythonExe $installed.pythonw
```

自定义安装时把 `$petRoot` 改为原安装目录。检查桌面版本和已安装插件：

```powershell
Get-Content -Raw -LiteralPath (Join-Path $petRoot 'install.json') | ConvertFrom-Json | Select-Object version,appRoot,dataDir
codex plugin list --marketplace codex-reset-pet
```

## 第一次使用

安装后，在 **新的 Codex 聊天** 中发送：

> 使用 reset-reminder 插件，把我的账户额度重置和重置卡到期信息同步到已安装的桌面小精灵，只同步一次，不创建定时任务。

首次同步之前，窗口显示“等待账户同步”，不会带入发布者的账户信息。v0.4.3 也可点击“刷新”，通过已登录的 Codex CLI 获取额度和重置时间；重置卡到期明细仍需完整账户同步。

想自动同步时，再单独告诉 Codex：

> 每小时同步一次桌面小精灵的账户状态，同时检查 Tibo 重置消息；只有需要提醒时通知我。

以后可说“关闭重置提醒的定时任务”。自动检查依赖电脑开机、Codex 运行及可用网络和额度，并非独立后台账户服务。

## 使用方式

| 操作 | 效果 |
| --- | --- |
| 点击人物 | 挥手/眨眼，同时展开或收起气泡；每第三次点击鼓脸 |
| 拖拽人物 | 移动窗口，显示惊讶和倾斜动作 |
| 松开拖拽 | 开心弹跳，再回到待机 |
| 10 秒无互动 | 直接进入并持续保持睡眠，头顶循环冒出由小变大的 zzz |
| 睡眠时点击或拖动 | 唤醒并响应操作；按住期间不会入睡 |
| 点击“刷新” | 从已登录的 Codex CLI 获取最新额度和重置时间，过程中不阻塞动画 |
| 点击 `tibo reset` | 默认浏览器打开 [Tibo 页面](https://codex-reset.com/zh/tibo) |
| 点击 `更新预估`（未发布源码功能） | 立即更新第三张卡片的 Tibo 网站预告 |
| 点击气泡的 × | 只收起气泡 |
| 右键人物 → 退出桌面小精灵 | 退出程序 |

两项日期和剩余时长按临近程度分别变色，人物保留原始配色。动画状态直接切换，不插入其他表情；目标刷新率 60Hz，实际表现取决于电脑负载。账户快照超过 90 分钟会显示待同步提示；时间仍按记录的截止时间变色，颜色只表示临近程度，不代表账户数据已重新核实。

账户卡片还显示“剩余额度 XX%”和进度条，数值为 Codex 官方账户状态的 `100 - usedPercent`，随账户快照更新。无数据时显示 `--`，过期快照标记“上次同步”。窗口每 5 秒重读本地数据，每 0.5 秒重算倒计时，这两个操作不会请求账户。点击“刷新”才通过 Codex 的 `account/rateLimits/read` 接口获取最新额度，不开启定时任务，也不发起模型对话。刷新中禁止重复点击，失败会提示并保留上次数据。

手动刷新数据保存在独立的 `desktop-usage.json`，不覆盖插件的完整 `usage.json`。窗口选择时间较新的额度；当前 CLI 可能只返回重置卡数量，不含到期明细，此时卡片标记“上次记录”，需要完整账户同步才能更新卡到期信息。

## 说明书和维护

未发布源码新增非语言合成语气音：点击、鼓脸、提起、落地和唤醒各有短音，入睡只播放一次 3 秒音效。待机及后台刷新保持安静；右键人物可关闭音效，设置会保存。无需额外音频依赖。

另支持本机个人 Amitaro 录音包：放在设置文件同目录的 `voice-amitaro` 文件夹，完整素材和清单齐备时自动启用，署名统一保留在 README 和素材说明中，桌面及右键菜单不显示署名。第三方录音不随仓库或安装包分发；使用与署名说明见 [语气音说明](docs/voice-credits.md)。

语气通过节奏、鼻音、开口音和气声区分。拖拽人物离起点达到 180 像素会额外触发一次开心短笑，每次拖拽只触发一次；立即松手也会保留正在播放的短笑，落地动画照常执行。

未发布源码修复了启动生命周期绑定：请通过 `start.ps1` 启动，程序由 Windows 本机进程创建接口独立启动，避免随启动器任务组清理而退出。运行状态每 30 秒记录心跳，主动关闭记录退出原因；启动失败可查看数据目录中的 `desktop-launcher.log`。

未发布源码支持右键人物 →“临期重置卡自动使用”：选择到期前 16–6 分钟，或前 5 分钟至到期。默认关闭，开启时绑定当前账户；只使用实时核对且临近到期的具体卡片。精灵关闭、电脑休眠或断网时无法保证执行；错过窗口不补用。

未发布源码另有“上次 Tibo 重置”卡片，显示最近重置时间、确认状态、网站公告说明和网站分类，点击说明可展开详情，也可点击“查看原帖”。网站分类仅供参考；历史和预估一起更新。

**未发布源码功能：**新增独立的“Tibo 预计重置”卡片，精灵启动时和运行期间每 5 分钟读取网站公开预估，也可点击“更新预估”。明确公告目标显示北京时间、倒计时和临近颜色；无目标显示“暂无明确预告”，不从概率推算日期。断网保留缓存并标注失败，超过 1 小时标注过期。不会发送账户数据或启用 Codex 定时任务；网站观测不代表本账户已到账。此功能尚未包含在 v0.4.3 发布包中。

- [完整说明书：数据同步、安装参数、更新、卸载及故障排查](docs/使用说明.md)
- [版本记录](CHANGELOG.md)
- [素材生成说明](plugins/reset-reminder/assets/生成说明.txt)

本仓库只包含程序、测试和角色素材，不包含账户快照、凭证、日志或个人定时任务。社区消息分为预告、待核实、社区确认和储备重置；社区确认不等于本人账户已到账。默认不自动使用重置卡；未发布源码新增需要主动开启的临期自动使用，详见说明书。

## 开发与测试

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s plugins/reset-reminder/tests -v
python scripts/build_release.py
```

90 项测试覆盖状态机、倒计时、重置卡筛选、消息去重、断网重连、超时取消、异常响应、保存失败、Tibo 预估解析及 Windows 原生窗口布局和刷新回归。非 Windows 环境会跳过原生窗口集成测试。详见 [异常处理测试记录](docs/异常处理测试.md)。发布包和校验文件生成在 `dist/`，构建使用明确的文件列表，排除运行数据和缓存。

双击人物新增“摸摸头”轻笑，右键也可触发。两次点击间隔不超过 300 毫秒且位置相近时识别为双击，只触发一次摸头，不切换气泡，也不计入每三次点击的鼓脸。单击等待 300 毫秒确认，拖动立即响应。

## 音效署名

个人可选录音包的声音来自 **あみたろの声素材工房（Amitaro’s Voice Material Studio）**：[作者网站](https://amitaro.net/)。感谢作者提供录音素材。录音遵循[作者使用条款](https://amitaro.net/voice/voice_rule/)，不属于本项目源码许可。仓库与安装包不包含这些第三方录音；默认提供项目合成音效。详细文件对应关系见[语气音与署名说明](docs/voice-credits.md)。
