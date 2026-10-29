# 语气音 / Voice notes

完整包默认使用当前选定的录音；原合成音仅作回退。声音属于作者，不属于本项目源码许可。

The complete package defaults to the selected recordings, with original synthesis as a fallback. Recordings retain the author's separate license.

## 完整包使用 / Complete package

v0.4.7 完整包内置 9 段语气音，解压后双击 `install.cmd` 即可安装或升级并启动；无需手动替换、迁移或下载录音。新安装及普通升级均无需执行导入命令。

The complete v0.4.7 package includes nine voice clips. Extract and double-click `install.cmd` to install/upgrade and launch, without manually replacing, moving, or downloading recordings. Fresh installations and ordinary upgrades do not require the import command.

`codex-pet sounds` 显示 `amitaro-bundled` 表示使用内置新版。旧版的 `data/voice-amitaro` 不删除，但不会自动遮盖内置音效。只有主动运行 `codex-pet sounds "音效文件夹"` 才使用个人覆盖，显示 `amitaro`。静音设置保留。内置录音损坏时回退到有效个人包或原合成音，诊断命令会报告原因。

`amitaro-bundled` in `codex-pet sounds` means the included current voices. Existing `data/voice-amitaro` folders are retained but do not automatically override included audio. An explicit `codex-pet sounds "voice-folder"` import selects a personal override (`amitaro`). Mute preferences persist. Damaged bundled files fall back to a valid personal pack or original synthesis, with diagnostics.

## Amitaro 个人录音包 / Personal recording pack

Voice: **Amitaro's Voice Material Studio — あみたろの声素材工房** ([official site](https://amitaro.net/)).

录音适用作者的[日文使用条款](https://amitaro.net/voice/voice_rule/)及[英文说明](https://amitaro.net/voice/terms/)，不属于本项目源码许可，也不是 CC0。录音仅作为完整应用的资源内置，不单独发布素材包。对外发布含录音的应用之前，应核对作者当前的署名、打包和使用报告要求。

Recordings have separate author terms, are not CC0, and are not covered by this project's source license. Recordings are included as complete-application resources, not as a standalone asset collection. Review current attribution, packaging, and usage-report requirements before publishing an application that includes recordings.

本机已准备的包位于设置文件旁的 `voice-amitaro`，包含 `manifest.json`（`provider` 为 `amitaro`）、`CREDITS.txt` 及以下 WAV 文件。主动导入的完整个人包才覆盖内置新版；无效时使用内置音效或原合成音。右键人物可静音，设置会保存；署名及作者链接统一放在中英文 README 和本说明中，界面不显示。

A prepared local pack lives in `voice-amitaro` beside the settings file, with `manifest.json` (`provider: amitaro`), `CREDITS.txt`, and the WAV files below. Explicitly imported personal packs override included voices; invalid personal files fall back to included voices or original synthesis. Right-click to mute; the preference is saved. Attribution and author links appear in both READMEs and this document, not in the desktop interface.

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

## 维护者发布记录 / Maintainer distribution record

作者日文条款允许按条件随应用同捆，要求署名/条款链接，以及公开或开始使用后约一个月内发送使用报告；内容大幅修改需事先咨询。作者日英文条款的条件不同，请按适用条款处理再分发。这里不表示作者为本项目背书或已单独确认本项目。当前尚未发送使用报告；维护者需完成这一项，不能把自动发布成功当作报告已完成。

The Japanese terms describe conditional application bundling, attribution/terms links, and a usage report around one month after publication or first use; substantial content edits require prior consultation. The Japanese and English terms differ; follow the terms applicable to your reuse. No author endorsement or individual approval is claimed. The usage report has not yet been sent; the maintainer must complete it separately. Successful automated publication is not proof that this report was sent.
