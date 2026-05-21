---
name: image_api
description: "Use when user asks to generate, edit, reference, mask, verify, or deliver raster images through the image_api Hermes skill/CLI."
version: 4.2.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [image-generation, image-editing, openai-compatible, responses-api, hermes-skill]
    related_skills: [hermes-agent-skill-authoring, skill-creator, writing-skills]
---

# image_api

## Overview

`image_api` 是一个 Hermes runtime skill + Python CLI，用来通过 OpenAI-compatible 图片接口生成图片、编辑图片、多参考图编辑和 mask 编辑。

本 `SKILL.md` 是 **agent runtime 行为契约**。它只保留执行时必须知道的路径、决策和安全边界；详细字段、provider 兼容性、故障排查和用户文档按需打开 `references/` 或 README。这是按 Skill Creator 的 progressive disclosure 原则整理后的结构。

公共表面必须保持 provider-agnostic：不要写真实 provider、私有模型路由、真实 key、私有 chat id 或本地专用路径。canonical identity 始终是 `image_api`；保留 underscore，不把 `/skill image_api`、runtime 路径或示例改成 hyphen 形式。

## When to Use

使用本 skill：

- 用户要求根据文字 prompt 生成 raster image。
- 用户要求改图、换背景、把人物/物体放入场景，且提供图片路径、URL、data URL 或当前会话附件。
- 用户提供多张参考图，需要主体图 + 额外参考图合成、迁移风格或保留主体。
- 用户要求局部编辑、mask、透明背景、尺寸、质量、格式或数量参数。
- 用户反馈图片没收到、质量被压缩、API 模式不匹配或 provider 返回非标准错误。

不要使用本 skill：

- 只描述、识别、OCR 或分析图片内容；使用 vision/OCR 工具。
- 生成视频、音频、PPT、SVG 架构图或其他非 raster image；使用对应 skill。
- 询问 Hermes `/fast`、priority processing、模型路由或 agent 配置；那不是图片快速基线。

## Runtime Authority

优先级：当前用户请求 > 当前附件/文件事实 > 本 `SKILL.md` > `references/` > README/CHANGELOG。

核心规则：

1. **参数足够就执行。** 缺 prompt 或编辑图片来源时才追问。
2. **Prompt 原样直传。** 不翻译、不润色、不扩展，除非用户明确要求优化 prompt。
3. **图片 + 文字默认是编辑/参考。** 直接用 `--edit --image`；不要先 vision 描述图片，除非用户要求识别/描述。
4. **始终用 `--json`。** 解析 JSON，不只看退出码或 stdout 文本。
5. **成功前验证文件。** 检查 `ok=true`、`paths` 非空、文件存在且 magic header 是 PNG/JPEG/WebP。
6. **失败暴露真实错误。** 鉴权、额度、参数、内容安全、超时、通用 upstream 错误不要靠切 API 模式掩盖。
7. **完成即交付。** 成功后发送图片/文件；失败给简短错误和下一步。不要输出 env、key、完整本地路径清单或 provider 私有信息。
8. **不写临时任务进 memory。** 不保存生成结果、prompt、路径或失败记录，除非用户明确要求保存长期偏好。

## Workflow

1. **选择任务类型**
   - 无图片输入：text-to-image generation，需要 prompt。
   - 有图片输入：image edit/reference，需要 prompt + 主图。
   - 有 mask：mask edit，加 `--mask`，必要时 `--validate-mask` 或 `--fix-mask-alpha`。

2. **选择图片参数**
   - 默认快速基线：`--quality low --size 1024x1024 --format png --moderation low`。
   - 高清/高质量：`--quality high`。
   - 正方形：`--size 1024x1024`；竖版：`1024x1536`；横版：`1536x1024`。
   - 透明背景：`--background transparent`；若 provider/model 不支持，报告限制，不改 prompt。
   - 生成多张：`--n N`；Responses 模式通常只支持单张，需要时循环请求。

3. **执行并验证**
   - 用 terminal 在稳定 `workdir` 中执行 CLI。
   - 解析 JSON，验证本地文件和图片 magic header。
   - 投递图片；如平台压缩或用户要原图，同时发送预览 + 原始文件附件。

## Quick Recipes

运行前加载 Hermes env：

```bash
ENV_FILE="$(hermes config env-path 2>/dev/null || printf '%s\n' ~/.hermes/.env)"
set -a
[ -f "$ENV_FILE" ] && source "$ENV_FILE"
set +a
```

文生图：

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  "<prompt>" \
  --size 1024x1024 \
  --quality low \
  --format png \
  --moderation low
```

单图编辑/参考图生成：

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image "<image-path-or-url>" \
  "<prompt>" \
  --size 1024x1024 \
  --quality low \
  --format png \
  --moderation low
```

多参考图编辑：

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image "<primary-subject>" \
  --ref "<reference-1>" \
  --ref "<reference-2>" \
  "<prompt>" \
  --size 1024x1024 \
  --quality low \
  --format png \
  --moderation low
```

mask 编辑：

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image "<source-image>" \
  --mask "<mask-image>" \
  --validate-mask \
  "<prompt>" \
  --size 1024x1024 \
  --quality low \
  --format png
```

如果 provider 要求某次调用使用特定模型，只在该次调用加 `--model <provider-specific-image-model>`；不要为了修复一次 model/route 错误永久改全局 `IMAGE_MODEL`。

## Configuration

公开示例只能使用占位符：

```bash
IMAGE_API_BASE=https://api.example.com/v1
IMAGE_API_KEY=YOUR_PROVIDER_API_KEY
IMAGE_MODEL=your-image-capable-model
IMAGE_API_MODE=auto
IMAGE_OUT_DIR=/tmp/image_api
```

配置规则：

- `IMAGE_API_BASE`：provider base URL，推荐通用 `/v1` base；Responses-only provider 可使用 `/v1/responses` 形态。
- `IMAGE_API_KEY`：provider API key，只放本地 env/secret store。
- `IMAGE_MODEL`：provider-specific image-capable model；未配置时必须单次传 `--model <provider-specific-image-model>`。
- `IMAGE_API_MODE`：`auto`、`images`、`responses`；默认 `auto`。
- `IMAGE_OUT_DIR`：输出目录，默认 `/tmp/image_api`。

## API Mode and Fallback Boundary

模式：

- `images`：generation 走 `/images/generations`，edit 走 `/images/edits`。
- `responses`：走 `/responses` + `image_generation` tool。
- `auto`：推荐默认；普通 `/v1` base 先尝试 Images API；明确配置 responses 时使用 Responses API。

只在这两类情况从 `images` 自动 fallback 到 `responses`：

- `/images/*` 明确不存在，例如 404。
- provider 返回成功形态但没有可用图片 payload。

不要在以下情况 fallback：鉴权错误、额度/限流、参数 schema、内容安全、超时、断流、5xx 或通用 upstream failure。base URL 已指向 `/responses` 时，不要强制 `--api-mode images`。

详细 payload 与 provider 行为按需打开 `references/providers/responses-api-compatibility.md`、`references/providers/responses-only-provider.md` 或 `references/providers/generic-images-api-quirks.md`。

## Output and Delivery

验证成功必须满足：

- JSON 可解析且 `ok` 为 `true`。
- `paths` 至少包含一个本地文件路径。
- 每个路径存在、大小大于 0，且文件头是 PNG、JPEG 或 WebP。
- `used_params.api_mode` 与预期一致；若 auto fallback 生效，只说明“已自动切到兼容模式”，不泄露 provider 私有细节。

交付规则：

- 普通交付：最终回复包含实际 `MEDIA:<path>`，让 gateway 原生发送图片。
- 用户关心原图质量或平台会压缩：发送预览图 + 同一路径的原始文件附件。
- `MEDIA:<path>` 与 `[[as_document]]` 是 Hermes/gateway 内部投递指令；不要把真实本地路径放进解释文本或代码块。
- 若投递失败但文件存在，降级为文件附件，并说明“已改用原文件附件发送”。

## Resource Map

核心执行：

- `scripts/image_api.py` — 唯一 CLI 执行入口；agent 调用时使用 `--json`。
- `scripts/validate_skill_docs.py` — 离线结构/隐私/runtime surface 验证。
- `tests/test_responses_mode.py` — API mode、Responses payload、fallback、CLI surface 回归测试。

按需参考：

- `references/api/fields.md` — 字段、自然语言到参数映射、交互规则。
- `references/api/resolution-guide.md` — 分辨率约束和边界案例。
- `references/providers/provider-quirks.md` — provider 非标准行为通用模板。
- `references/providers/generic-images-api-quirks.md` — Images API provider 兼容性。
- `references/providers/responses-api-compatibility.md` — Responses API payload 与测试策略。
- `references/providers/responses-only-provider.md` — Responses-only provider 配置模板。
- `references/troubleshooting/image-delivery-debugging.md` — 用户说“图片没收到”时的诊断流程。
- `references/troubleshooting/gateway-image-debug.md` — 交互式 gateway 图片路由排查。
- `references/provider-timeout-debugging.md` — HTML/非 JSON/超时响应的脱敏排查。
- `references/fast-mode-verification.md` — image_api 快速基线验证。
- `references/fast-term-disambiguation.md` — 区分 Hermes `/fast` 与 image_api 快速基线。
- `references/hermes-chat-original-delivery.md` — 预览图 + 原始文件附件投递模式。

用户/维护者文档：

- `README.md` / `README.zh-CN.md` — 安装、配置、CLI 参数、项目结构和用户-facing 文档。
- `CHANGELOG.md` / `CHANGELOG.zh-CN.md` — 可读变更记录。
- `.env.example` — provider-agnostic 本地配置模板。
- `LICENSE` — 许可证。

没有 `assets/` 是刻意选择：当前 skill 不需要可复用图片模板、字体或二进制资产；不要为空目录增加噪声。

## Troubleshooting Escalation

- 用户说图片没收到：先检查 JSON `paths`、本地文件、magic header、gateway 投递结果；按 `references/troubleshooting/image-delivery-debugging.md`。
- provider 返回非 JSON、HTML、超时或 upstream：先脱敏，再按 `references/provider-timeout-debugging.md`。
- API 模式或 payload 不匹配：按 provider references；不要把 provider-specific 模型写成通用默认。
- Hermes `/fast` 与图片 fast 混淆：按 `references/fast-term-disambiguation.md`。
- shell 报 cwd 不存在：terminal 调用显式设置稳定 `workdir`。

## Common Pitfalls

1. **先 vision 再改图。** 用户把图片当素材时直接 edit/reference；vision 只用于识别/描述。
2. **只看退出码。** 必须解析 JSON 并验证输出文件。
3. **错误 fallback。** 只有 endpoint 缺失或空图片 payload 才 fallback。
4. **全局改模型修一次错。** 单次用 `--model`；持久 env 改动要用户同意。
5. **展示内部投递 marker 或真实路径。** 只把 `MEDIA:<path>` 用作实际投递指令。
6. **写入 provider-specific 公共默认。** 公开示例只用占位 host、key 和 model。
7. **忽略 underscore 身份。** `image_api` 是 canonical runtime identity。

## Verification Checklist

- [ ] `SKILL.md` 从 byte 0 开始就是 `---`，frontmatter 有 `name`、`description`、`version`、`author`、`license`、`metadata.hermes.tags`。
- [ ] `name: image_api`、路径和示例均保留下划线身份。
- [ ] description 以 “Use when ...” 开头且长度小于 1024。
- [ ] SKILL/README/public references 不含真实 key、私有 provider、私有模型路由或本地专用配置名。
- [ ] 示例 key 使用 `YOUR_PROVIDER_API_KEY`，示例模型使用 `your-image-capable-model`。
- [ ] `PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/validate_skill_docs.py` 通过。
- [ ] `python3 -B` + `py_compile.compile(..., cfile=/tmp/...)` 验证 Python 文件且不在 skill tree 留 `.pyc`。
- [ ] `PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest -p no:cacheprovider tests/test_responses_mode.py -q` 通过。
- [ ] 如改动 source repo，还要同步到 `~/.hermes/skills/image_api`，并在新会话重新 `/skill image_api`。
