# 语气音 / Voice notes

内置默认音效为项目生成的合成短音。个人安装可选用独立录音包，与默认合成音分开保存。

The bundled default sounds are synthesized for this project. A personal recording pack can override them locally.

## 安装与跨设备迁移 / Install and transfer

需要桌面版本 **v0.4.6 或以上**。在 PowerShell 运行 `codex-pet sounds` 可查看配置的音效、文件夹，以及运行实例的音效和静音状态。`original-synthesis` 是默认合成音，`amitaro` 是个人录音。程序更新保留个人音效，但不会自动下载、安装或替换它。静音偏好也不会因导入而改变。

Requires desktop **v0.4.6 or later**. Run `codex-pet sounds` in PowerShell to inspect the configured pack, its location, and the running pet's audio/mute status. `original-synthesis` means bundled audio; `amitaro` means personal recordings. Updating preserves an existing personal pack, but never downloads, installs, or replaces it automatically. Importing does not change your mute preference.

**已有本机音效 / Already have the voices on your own device:**

1. 从原设备复制 `%LOCALAPPDATA%\CodexResetPet\data\voice-amitaro` 整个文件夹到你的另一台设备，例如 `D:\voice-amitaro`。自定义安装的位置用 `codex-pet sounds` 查询。只复制这个文件夹，不复制 `usage.json`、设置或账户数据；不上传录音到 GitHub 或公开分享。
2. 在新设备右键退出小精灵，运行下方导入命令。导入保留 WAV 原样，效果与原设备一致；之后启动。

Copy the entire `voice-amitaro` folder from your own original device to your other device, for example `D:\voice-amitaro`. Locate custom installations with `codex-pet sounds`. Copy only the voice folder, not account files or settings; do not publish recordings on GitHub or share a standalone pack. Quit the destination pet through its right-click menu, import, then start. Prepared WAV files are copied without audio changes.

```powershell
codex-pet sounds "D:\voice-amitaro"
codex-pet
```

**没有现成音效 / Starting from the originals:**

先阅读[日文条款](https://amitaro.net/voice/voice_rule/)或[英文条款](https://amitaro.net/voice/terms/)，在[作者素材页面](https://amitaro.net/voice/game_01/)下载下面六个 WAV，放在同一个文件夹（不要改名），然后将其路径传给同一命令。作者禁止外部工具直接下载其服务器上的录音，因此本命令仅离线读取本地文件。署名保留在本文、README 和生成的 `CREDITS.txt` 中。

Read the [English terms](https://amitaro.net/voice/terms/) or [Japanese terms](https://amitaro.net/voice/voice_rule/), download these six WAV files on the [author's materials page](https://amitaro.net/voice/game_01/), and place them together without renaming. Pass that folder to the same import command. The author prohibits direct downloads from external tools; this command reads local files only. Credits are retained here, in the README, and in the generated `CREDITS.txt`.

| 原文件 / Original | 页面分类 / Page category |
| --- | --- |
| `fufu_02.wav` | 102_reaction |
| `ehehe_01.wav`、`nmou_03.wav`、`aha_01.wav` | 106_kanjou |
| `akubi_03.wav` | 195_serifu_others |
| `n_02.wav` | 101_henji |

```powershell
codex-pet sounds "D:\downloaded-originals"
codex-pet
```

原始录音会校验 SHA-256，再在本机生成下表对应音效；不改变音高或语速，不额外安装音频依赖。缺少/损坏文件、原素材版本不同或写入失败会报错，原包保留。先修复来源再重试，不要通过更名把其他音效冒充指定原音。整个流程无需联网；仅手动获取素材和更新程序需要联网。

Originals are checked against SHA-256 hashes before the mapped clips below are built locally. No pitch/tempo changes or extra audio dependencies are used. Missing/corrupt files, changed originals, or write failures report an error and preserve the previous pack. Correct the source and retry; do not rename a different recording to bypass selection. Import is offline; obtaining the originals and updating the app require network access.

使用 `-NoPath` 安装时，将上述 `codex-pet` 换成 `& "$env:LOCALAPPDATA\CodexResetPet\bin\codex-pet.cmd"`；自定义目录使用对应 `bin\codex-pet.cmd`。源码/手动 ZIP 安装后同样可用此入口。只更新 Codex 聊天插件不会安装桌面命令，需按 README 更新桌面程序。

With `-NoPath`, replace `codex-pet` with `& "$env:LOCALAPPDATA\CodexResetPet\bin\codex-pet.cmd"`, or your custom installation's `bin\codex-pet.cmd`. Source/manual ZIP installations provide the same command after installation. Updating only the chat plugin does not install the desktop command; update the desktop app as described in the README.

## Amitaro 个人录音包 / Personal recording pack

Voice: **Amitaro's Voice Material Studio — あみたろの声素材工房** ([official site](https://amitaro.net/)).

录音适用作者的[日文使用条款](https://amitaro.net/voice/voice_rule/)及[英文说明](https://amitaro.net/voice/terms/)，不属于本项目源码许可，也不是 CC0。此仓库不包含或重新分发这些录音。对外发布含录音的应用之前，应核对作者当前的署名、打包和使用报告要求。

Recordings have separate author terms, are not CC0, and are not covered by this project's source license. This repository does not redistribute them. Review current attribution, packaging, and usage-report requirements before publishing an application that includes recordings.

本机已准备的包位于设置文件旁的 `voice-amitaro`，包含 `manifest.json`（`provider` 为 `amitaro`）、`CREDITS.txt` 及以下 WAV 文件。完整包自动启用；缺少文件或清单无效时回退默认合成音。右键人物可静音，设置会保存；署名及作者链接统一放在中英文 README 和本说明中，界面不显示。

A prepared local pack lives in `voice-amitaro` beside the settings file, with `manifest.json` (`provider: amitaro`), `CREDITS.txt`, and the WAV files below. Missing files or an invalid manifest fall back to bundled sounds. Right-click to mute; the preference is saved. Attribution and author links appear in both READMEs and this document, not in the desktop interface.

| 文件 / File | 触发 / Trigger | 原录音 / Original |
| --- | --- | --- |
| click_1.wav | 点击轻笑 / Tap | fufu_02.wav |
| click_2.wav | 交替俏皮笑 / Alternate tap | ehehe_01.wav |
| pout.wav | 鼓脸嗔怒 / Annoyed pout | nmou_03.wav |
| drag.wav | 提起轻笑 / Playful pickup | fufu_02.wav |
| drag_happy.wav | 拖离起点 180 像素，一次 / Drag 180 pixels, once | aha_01.wav |
| land.wav | 落地开心笑 / Happy landing | ehehe_01.wav |
| sleep.wav | 入睡短哈欠，一次 / Sleep, once | akubi_03.wav |
| pet.wav (optional) | 双击摸头 / Double-tap head pat | fufu_02.wav + ehehe_01.wav |
| wake.wav | 唤醒轻哼 / Wake | n_02.wav |

个人安装保留原音高和语速，仅降低音量并处理边缘；睡眠短哈欠之后补静音至 3 秒，不重复哈欠。松手不截断尚未结束的开心音。音效从本地播放，不调用语音生成服务。

The personal installation preserves pitch and tempo, with reduced gain and short edge fades. The sleep yawn is padded with silence to three seconds and never looped. Releasing a drag does not cut off the happy clip. Playback is local and makes no speech-generation requests.

摸头音将两段已有轻笑以 100 毫秒静音连接并稍降音量，约 1.76 秒；不改变音高和语速。旧音效包缺少 `pet.wav` 时使用第二段点击轻笑。

The head-pat clip joins two existing laughs with 100 ms silence at a reduced volume, about 1.76 seconds, without pitch or tempo changes. Older packs without `pet.wav` fall back to the second tap laugh.

鼓脸使用完整的「んもぅ～っ」录音，约 1.89 秒，不拼接笑声；保留原音高和语速。

The pout uses one complete nmou_03.wav recording, about 1.89 seconds, without an appended laugh or pitch/tempo changes.
