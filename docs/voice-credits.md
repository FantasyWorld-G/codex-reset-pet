# 语气音 / Voice notes

内置默认音效为项目生成的合成短音。个人安装可选用独立录音包，与默认合成音分开保存。

The bundled default sounds are synthesized for this project. A personal recording pack can override them locally.

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
