---
name: image_api
description: Generate and edit images using image_api. Generic wrapper that works with any OpenAI-compatible image provider. Handles auth via env vars, retry on transient failures, resolution constraints, prompt verbatim passing, and content moderation.
version: 4.1.0
---

# image_api

使用 image_api 生成或编辑图片。不绑定任何 provider，通过环境变量配置。

## Agent 行为规范

1. **直接执行** — 参数够就调用，不解释流程、不复盘步骤
2. **缺字段才追问** — 只缺 prompt 或图片来源时才问用户，可选字段用默认值
3. **完成即结束** — 成功就发图，失败就报错。不存 memory、不输出参数、不解释原理
4. **Prompt 原样直传** — 不翻译、不优化、不扩展，除非用户明确要求
5. **不为简单任务加戏** — "生成一张猫的图片" → 调脚本 → 发图 → 完

## 执行流程

```
① 判断：文生图(prompt) or 改图(prompt + image)
② 缺必填字段 → 追问；够了 → 直接执行
③ terminal 调用脚本（必须 --json）
④ 成功 → MEDIA:发图；失败 → 报错
⑤ 结束。不存 memory，不输出多余内容。
```

## 调用命令

**文生图：**
```bash
source ~/.hermes/.env && export IMAGE_API_KEY IMAGE_API_BASE
python3 ~/.hermes/skills/image_api/scripts/image_api.py --json "<prompt>" --size <size> --quality low --format png --moderation low
```

**改图：**
```bash
source ~/.hermes/.env && export IMAGE_API_KEY IMAGE_API_BASE
python3 ~/.hermes/skills/image_api/scripts/image_api.py --json --edit --image "<path>" "<prompt>" --size <size> --quality low --format png --moderation low
```

**多参考图编辑：**
```bash
source ~/.hermes/.env && export IMAGE_API_KEY IMAGE_API_BASE
python3 ~/.hermes/skills/image_api/scripts/image_api.py --json --edit --image "<main>" --ref "<ref1>" --ref "<ref2>" "<prompt>" --size <size> --quality low --format png --moderation low
```

## API 模式

Provider-specific compatibility notes belong in `references/`; the runtime instructions below stay provider-agnostic.

支持三种互不混用的后端模式：

- `images`：原始 OpenAI Images API，走 `/images/generations` 与 `/images/edits`，保持原功能不变。
- `responses`：Responses API，走 `/responses` + `image_generation` tool，适合只通过 Responses 形态开放图片能力的 provider。
- `auto`：默认模式。若 `IMAGE_API_MODE=responses` 或 `IMAGE_API_BASE` 直接写到 `/responses`，自动使用 `responses` 并把 base 规范化为 `/v1`；否则先尝试 `images`。如果 `/images/*` endpoint 不存在或返回空图片，再自动切到 `responses` 重试。

自动纠错规则：如果 base 指向 `/responses` 却强制 `--api-mode images`，脚本会拒绝执行，避免把 Images API endpoint 拼成错误路径。不要因鉴权、配额、参数、内容安全、超时或通用上游错误而自动切模式；这些是真实错误，应直接暴露。

通用配置示例：
```bash
IMAGE_API_BASE=https://api.example.com/v1
IMAGE_API_KEY=sk-your-provider-key
IMAGE_MODEL=your-image-capable-model
IMAGE_API_MODE=auto
```

responses 模式注意：`n>1`、部分 provider 的 `background=transparent` 可能不可用；需要多张图时循环多次请求。保存文件时按图片 magic header 判断真实格式，避免 provider 声称 webp 但实际返回 png。

## 默认参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| quality | low | 用户未指定时用 low |
| format | png | — |
| moderation | low | 用户强制要求 |
| size | 1024x1024 | 证件照用 1024x1536 |
| timeout | 900s | 脚本内置，通常不需要调 |

## 自然语言 → 参数映射

- `高清` → `--quality high`
- `透明背景` → `--background transparent`
- `1:1` → `--size 1024x1024`，`3:4` → `--size 1024x1536`，`4:3` → `--size 1536x1024`
- `4k` → `--size 3840x1920`（横）或 `--size 1920x3840`（竖）
- `生成N张` → `--n N`

## 发送方式

成功后通过 `MEDIA:/tmp/gptimage/xxx.png` 发送。Telegram 自动处理。

**高质量投递（推荐）：** Telegram 会压缩图片消息。对于生成/编辑结果，尽量同时发送：
1. 图片预览 — `send_message` 用 `MEDIA:` 路径，方便内联查看
2. 原文件附件 — 同路径再发一次作为文件，保留原始画质

如果图片消息投递失败但文件存在，降级为发送文件附件。

## 参考图工作流（--edit 模式）

**单参考图：** `--image` 传入一张图，API 直接看到像素。

**多参考图（v4.1.0）：** `--ref` 可重复传入多张参考图，底层用 `image[]` multipart 字段发送。
```bash
--edit --image 主图.png --ref 参考1.png --ref 参考2.png "prompt"
```

当用户说"把这个人加到那个场景里"：
- 选**人物图**作为 `--image`（主图）
- 场景图作为 `--ref`（参考图）
- 效果优于纯文字描述

当用户只发了一张图并说"用这张图生成"：
- 默认使用 `--edit` 模式，图片作为参考
- 不需要先描述图片内容再生成，直接调 API

当用户发图但没说要做什么：
- 先问用户想要生成什么样的图

## Agent 行为纠正

当用户发图并说"把她加进去"/"以这张图为参考"时，意图是**用该图作为 `--edit --image` 的参考图**，不是让你先分析图片再描述。不要对用户发的参考图调用 vision_analyze，除非用户明确要求你描述图片内容。

## 关键陷阱

1. **terminal cwd 被删除** — 清理临时目录前先 `cd /root`，否则后续所有 terminal 调用报 FileNotFoundError。已坏时用 `execute_code + subprocess.run(cwd="/root")` 绕过
2. **API Key 无效返回 "Upstream request failed"** — 部分 provider 对错误 key 不返回 401 而是 upstream failed，先验证 key 再重试
3. **edit 模式 stream disconnected** — 部分 provider 不稳定，脚本自动重试 2 次。仍失败则降级 generate
4. **分辨率约束** — 宽高必须是 16 的倍数，最长边 ≤ 3840px，总像素 655K~8.3M，宽高比 ≤ 3:1（脚本预校验，不等 API 报错）
5. **mask 校验** — `--validate-mask` 检查 mask 尺寸/alpha；`--fix-mask-alpha` 自动把灰度 mask 转 RGBA alpha mask（需要 Pillow）
5. **mimo-v2.5 vision 有严重幻觉** — mimo-v2.5 作为 vision 模型会编造场景（如把灰色背景编成户外、虚构粉色手机壳等）。不要用 mimo-v2.5 做图片描述。mimo-v2.5-pro 的 vision 准确
6. **mimo-v2.5-pro 不支持 inline 图片** — mimo-v2.5-pro 作为主模型时，gateway 以 base64 image_url 格式 inline 附图会被静默丢弃（不报错、不处理）。解决：设 `image_input_mode: text`，让图片先经 vision_analyze 预处理为文本描述再传入对话
7. **auxiliary.vision 设 base_url 导致 provider 解析为 "custom"** — 当 auxiliary.vision.base_url 非空时，代码将 provider 强制设为 "custom"，使用 OPENAI_API_KEY 而非实际 provider 的 key，导致 401。解决：base_url 留空，让 auto-detect 正确解析 provider
8. **用户发了图但模型没收到** — Telegram 网关有时缓存了图片但未传入模型上下文。症状：用户说"用这张图"但对话中没有图片附件。排查：`ls -lt ~/.hermes/image_cache/` 找最新文件，`grep "Image routing\|Flushing photo\|Cached user photo" ~/.hermes/logs/gateway.log` 确认网关是否收到。找到路径后直接用 `--edit --image "<path>"` 生成
9. **用户发图时的意图判断** — 用户在图片生成对话中发图片+文字，大概率是要用图作为参考/编辑素材，不是让你描述图片内容。如果消息含图片但你只看到文字描述，先怀疑图片丢失而非用户没发图

## 详细参考

- `references/fields.md` — 字段映射、安全替换表
- `references/provider-quirks.md` — Provider 非标准行为
- `references/resolution-guide.md` — 分辨率约束完整数据
- `references/image-delivery-debugging.md` — 用户说"图片没收到"时的诊断流程
- `references/freemodel-responses.md` — provider-specific Responses API 图片生成、改图、mask、参数兼容与防混用规则
- `references/freemodel-responses-api.md` — provider-specific `/v1/responses` 图片生成/改图兼容性、参数映射与适配注意事项
