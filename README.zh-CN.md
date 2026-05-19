# image_api

[English](README.md) | 简体中文

`image_api` 是一个轻量级 Hermes skill 和命令行工具，用于通过 OpenAI-compatible provider 生成图片和编辑图片。

它的设计目标是 provider-agnostic：配置 base URL、API key 和模型后，就可以用同一套 CLI 完成文生图、改图、多参考图编辑、mask 编辑和结构化 JSON 输出。它同时支持经典 Images API 形态和较新的 Responses API 图片工具形态，并提供安全的自动识别机制，让用户不必先知道 provider 到底开放了哪个图片端点。

## 核心特性

- 通过 OpenAI-compatible Images API (`/images/generations`) 文生图。
- 通过 Images API (`/images/edits`) 改图，支持本地文件、远程 URL 和 data URL。
- 支持 Responses API：`/responses` + `image_generation` tool。
- `auto` API 模式：先尝试标准 Images API；仅当 Images 端点不存在或没有返回图片数据时，才 fallback 到 Responses API。
- 多参考图编辑：可重复传入 `--ref`。
- 可选 mask，并支持 mask 校验和 alpha 通道修复。
- 对尺寸、质量、格式、压缩、背景、审核级别、生成数量等参数做 provider-safe 处理。
- 同时解析 `b64_json` 和 URL 图片响应。
- 按图片 magic header 判断真实输出格式，避免 provider 标错格式时保存错误扩展名。
- 对 HTML/proxy 响应、JSON 错误、不支持的选项、端点混用、可重试上游错误给出明确诊断。
- `--json` 结构化输出，适合 Hermes、cron job、脚本和其他自动化流程。

## 这个项目是什么

`image_api` 不是 Web 服务。它是一个打包成 Hermes skill 的小型 Python CLI：

```text
README.md / SKILL.md / references/  -> 使用说明和 provider 兼容性笔记
scripts/image_api.py                -> 确定性的图片 API 客户端
tests/                              -> API 模式行为的回归测试
```

运行依赖刻意保持很少：必需依赖是 `requests`；Pillow 仅在需要 mask 检查/修复时可选使用。

## 支持的 API 模式

`image_api` 有三种 API 模式：

- `auto` — 默认模式。根据配置和 provider 行为选择最安全的模式。
- `images` — 经典 OpenAI Images API：
  - 生成：`POST /images/generations`
  - 编辑：`POST /images/edits`
- `responses` — OpenAI Responses API 形态：
  - `POST /responses`
  - payload 包含 `tools: [{"type": "image_generation"}]`

### auto 模式行为

大多数用户应该保持不设置，或显式设置为：

```bash
IMAGE_API_MODE=auto
```

auto 模式规则：

1. 如果 `IMAGE_API_MODE=responses`，使用 Responses API。
2. 如果 `IMAGE_API_BASE` 以 `/responses` 结尾，使用 Responses API，并在内部规范化 base URL。
3. 否则先尝试标准 Images API。
4. 如果 Images 端点明确不可用，例如 `404 Not Found`，或返回中没有图片数据，则重试一次 Responses API。
5. 不会因为鉴权错误、额度错误、请求参数错误、内容安全错误、超时或通用上游失败而 fallback。这些错误应该直接暴露，否则切换端点会掩盖真实问题。

这样，非专业用户只需要配置普通 `/v1` base URL，不必提前理解 provider 的图片端点细节。

## 安装

### 从本地 checkout 安装为 Hermes skill

```bash
mkdir -p ~/.hermes/skills/image_api
cp -R ./* ~/.hermes/skills/image_api/
chmod +x ~/.hermes/skills/image_api/scripts/image_api.py
```

然后开启一个新的 Hermes session，或显式加载 skill：

```text
/skill image_api
```

### 直接作为 CLI 使用

也可以在仓库目录直接运行：

```bash
python3 scripts/image_api.py --help
```

## 配置

Hermes 约定把密钥放在当前 profile 的 env 文件里，通常是：

```text
~/.hermes/.env
```

可以用下面命令查看实际路径：

```bash
hermes config env-path
```

推荐的最小配置：

```bash
IMAGE_API_BASE=https://api.example.com/v1
IMAGE_API_KEY=sk-your-provider-key
IMAGE_MODEL=gpt-image-2
IMAGE_API_MODE=auto
```

如果 provider 只通过 Responses-style endpoint 暴露图片能力，也使用同样的通用配置：

```bash
IMAGE_API_BASE=https://api.example.com/v1
IMAGE_API_KEY=sk-your-provider-key
IMAGE_MODEL=your-image-capable-model
IMAGE_API_MODE=auto
```

如果 provider 要求显式写 endpoint path，也支持：

```bash
IMAGE_API_BASE=https://api.example.com/v1/responses
IMAGE_API_KEY=sk-your-provider-key
IMAGE_MODEL=your-image-capable-model
IMAGE_API_MODE=auto
```

不要提交真实 key。文档和 issue 示例应使用 `sk-your-provider-key` 这类占位符。

## 环境变量

- `IMAGE_API_BASE`：Provider base URL。必填。可用时优先用通用 `/v1` base。
- `IMAGE_API_KEY`：Provider API key。必填。
- `IMAGE_MODEL`：默认模型。可选；未设置时默认 `gpt-image-2`。
- `IMAGE_API_MODE`：`auto`、`images` 或 `responses`。可选；默认 `auto`。
- `IMAGE_OUT_DIR`：输出目录。可选；默认 `/tmp/gptimage`。

## 快速开始

加载环境变量后调用脚本：

```bash
set -a
source ~/.hermes/.env
set +a

python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  "A clean vector-style blue checkmark icon on a white background" \
  --size 1024x1024 \
  --format png
```

使用 `--json` 时输出结构化结果：

```json
{
  "ok": true,
  "paths": ["/tmp/gptimage/0520_120000_A_clean_vector_style_blue_check_0.png"],
  "used_params": {
    "mode": "generate",
    "model": "gpt-image-2",
    "size": "1024x1024",
    "quality": "low",
    "output_format": "png",
    "n": 1,
    "moderation": "low",
    "api_mode": "images"
  },
  "endpoint": "https://api.example.com/v1"
}
```

auto fallback 选择 Responses API 时，`api_mode` 可能是 `responses`。

## 常用命令

### 文生图

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  "A minimalist product photo of a matte black water bottle" \
  --size 1024x1024 \
  --quality high \
  --format png
```

### 改图

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image source.png \
  "Change the background to a soft studio gradient"
```

### URL 或 data URL 图片输入

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image https://example.com/source.png \
  "Make the object blue while preserving shape"
```

### 多参考图编辑

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image main.png \
  --ref palette.png \
  --ref style-reference.png \
  "Apply the color palette and style reference to the main image"
```

### Mask 编辑

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image source.png \
  --mask mask.png \
  --validate-mask \
  "Replace only the masked region with a red umbrella"
```

如果 mask 没有 alpha 信息，并且安装了 Pillow，可以在上传前修复：

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image source.png \
  --mask gray-mask.png \
  --fix-mask-alpha \
  "Edit the masked area only"
```

### 强制指定 API 模式

大多数用户不需要这样做。调试 provider 行为时可以使用：

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --api-mode images \
  "A small isometric house icon"

python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --api-mode responses \
  "A small isometric house icon"
```

## CLI 参数

- `prompt`：必填，图片描述或编辑指令。
- `--edit`：使用编辑模式。
- `--image`：主图片路径、URL 或 data URL。编辑模式必填。
- `--ref`：额外参考图，可重复传入。
- `--mask`：mask 图片路径、URL 或 data URL。
- `--model`：针对单次调用覆盖 `IMAGE_MODEL`。
- `--size`：图片尺寸，默认 `1024x1024`。如果 provider 支持，也可使用 `auto` 等特殊值。
- `--quality`：`low`、`medium`、`high` 或 `auto`。
- `--n`：生成数量。Images API 可能支持多张；Responses 模式当前要求为 `1`。
- `--format`：`png`、`jpeg` 或 `webp`。
- `--compression`：`0`-`100`，通常用于 `jpeg`/`webp` provider。
- `--background`：`opaque`、`auto` 或 `transparent`。部分 Responses provider 拒绝 `transparent`，客户端会阻止已知不安全组合。
- `--moderation`：`auto` 或 `low`。
- `--outdir`, `-o`：输出目录。
- `--prefix`：可选文件名前缀。
- `--timeout`：请求超时时间，单位秒。
- `--validate-mask`：编辑前检查 mask 尺寸和 alpha。
- `--fix-mask-alpha`：可行时把灰度 mask 转为 RGBA alpha mask。
- `--api-mode`：`auto`、`images` 或 `responses`。
- `--json`：输出结构化 JSON，便于自动化处理。

## 输出与文件处理

生成文件会写入 `IMAGE_OUT_DIR`、`--outdir` 或 `/tmp/gptimage`。

客户端会根据实际图片字节保存文件，而不仅依赖 provider 声明的 `output_format`。这很重要，因为有些 provider 可能声称返回 `webp` 或 `jpeg`，但实际字节是 PNG。

支持的输出字节签名：

- PNG：`89 50 4E 47`
- JPEG：`FF D8 FF`
- WebP：`RIFF .... WEBP`

## Provider 兼容性建议

公开文档和示例应使用通用配置。Provider-specific 的兼容性记录应放在 `references/`，不要反复写进 README 主叙事。

不同 provider 可能在这些方面不同：

- 图片生成是通过 Images API、Responses API，还是两者都支持；
- 编辑模式接受 multipart `image[]`、Responses `input_image`，还是 mask；
- 是否支持 `n > 1`；
- 是否支持透明背景；
- `quality`、`output_format`、`compression` 是否被严格执行；
- 返回图片字节是否与请求格式一致。

添加新 provider 时建议：

1. 把 `IMAGE_API_BASE` 配为普通 `/v1` URL。
2. 保持 `IMAGE_API_MODE=auto`。
3. 运行一次文生图 smoke test。
4. 如果 provider 声称支持编辑，再运行一次 edit test。
5. 只有当行为非标准时，才在 `references/` 下添加简短 provider note。

## 错误处理与重试策略

客户端会重试限流、网关错误、服务器错误等临时失败。它不会隐藏永久性错误。

Images API 到 Responses API 的 auto fallback 是刻意收窄的：

- 允许 fallback：图片端点缺失，或返回中没有图片数据。
- 不允许 fallback：错误凭据、额度失败、请求参数错误、内容安全响应、超时或通用上游错误。

这样既降低配置门槛，又不掩盖真实失败。

## 分辨率约束

客户端会在发送请求前校验常见 provider 约束：

- 最长边：`<= 3840`
- 总像素：约 `655,360` 到 `8,294,400`
- 宽高必须能被 `16` 整除
- 宽高比建议 `<= 3:1`
- 很大的竖图尺寸即使通过本地校验，也可能依赖 provider 能力

详见 `references/api/resolution-guide.md`。

## 测试

运行回归测试：

```bash
python3 -m pytest tests/test_responses_mode.py -q
python3 -m py_compile scripts/image_api.py
```

可选 live smoke test，前提是 `~/.hermes/.env` 中已有有效 provider 凭据：

```bash
set -a
source ~/.hermes/.env
set +a

python3 scripts/image_api.py \
  --json \
  "A tiny black plus icon on a white background" \
  --size 1024x1024 \
  --format png \
  --outdir /tmp/gptimage_smoke
```

## 项目结构

```text
image_api/
├── README.md
├── README.zh-CN.md
├── SKILL.md
├── CHANGELOG.md
├── CHANGELOG.zh-CN.md
├── LICENSE
├── .env.example
├── scripts/
│   └── image_api.py
├── tests/
│   └── test_responses_mode.py
└── references/
    ├── api/
    │   ├── fields.md
    │   └── resolution-guide.md
    ├── providers/
    │   ├── provider-quirks.md
    │   ├── generic-images-api-quirks.md
    │   ├── responses-api-compatibility.md
    │   └── responses-only-provider.md
    └── troubleshooting/
        ├── gateway-image-debug.md
        └── image-delivery-debugging.md
```

## 安全说明

- 将 API key 保存在 `~/.hermes/.env` 或其他本地 secret store 中。
- 不要提交 `.env` 文件或真实 provider key。
- 文档和 issue 里使用占位符。
- 生成图片应视为用户数据；除非用户明确要求，不要上传到其他地方。

## License

MIT

## Friend Link

[LinuxDo](https://www.linux.do)
