# image_api

通用图片生成与编辑工具，基于 OpenAI image_api (`/v1/images/generations` + `/v1/images/edits`)。

**轻量依赖**，Python + requests，不绑死任何 provider。

## 特性

- 🖼️ **文生图** + ✏️ **改图**（支持本地文件/URL/data URL）
- 🖼️ **多参考图编辑** — `--ref` 传入多张参考图，底层用 multipart `image[]`
- 🔄 **自动重试** — 临时错误（429/502/超时）自动重试 2 次
- 📊 **JSON 输出** — `--json` 模式输出结构化结果
- 🔍 **双格式支持** — 同时支持 `b64_json` 和 `url` 响应格式（自动检测并下载）
- 🛡️ **内容类型检查** — 检测 HTML 错误页面（网关错误/反爬拦截），给出明确提示
- ✅ **参数预校验** — 尺寸 16 倍数、最大边、总像素、宽高比预检，不等 API 报错
- 🎭 **Mask 校验与修复** — `--validate-mask` 检查尺寸/alpha，`--fix-mask-alpha` 自动修复灰度 mask
- ⚡ **延迟配置加载** — `--help` 不再因缺 env 报错
- 🔗 **请求追踪** — 每请求 UUID 追踪（`X-Client-Request-Id`）

## 快速开始

```bash
# 1. 配置环境变量（Hermes 推荐放在全局 ~/.hermes/.env）
# 编辑 ~/.hermes/.env，填入 IMAGE_API_BASE 和 IMAGE_API_KEY

# 2. 文生图
source ~/.hermes/.env && export IMAGE_API_KEY IMAGE_API_BASE
python3 ~/.hermes/skills/image_api/scripts/image_api.py --json "A beautiful sunset" --size 1024x1024 --quality high

# 3. 改图
python3 ~/.hermes/skills/image_api/scripts/image_api.py --json "Make it blue" --edit --image source.png

# 4. 多参考图编辑
python3 ~/.hermes/skills/image_api/scripts/image_api.py --json --edit --image main.png --ref ref1.png --ref ref2.png "Combine these"
```

## 输出格式

```json
{
  "ok": true,
  "paths": ["/tmp/gptimage/xxx.png"],
  "used_params": {
    "model": "gpt-image-2",
    "size": "1024x1024",
    "quality": "high",
    "n": 1
  },
  "endpoint": "https://your-provider.com/v1"
}
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `prompt` | 图片描述（必填） | - |
| `--edit` | 改图模式 | 否 |
| `--image` | 原图路径/URL/data URL（改图必填） | - |
| `--ref` | 参考图，可重复传入（多参考图编辑） | - |
| `--mask` | 遮罩图 | - |
| `--size` | 尺寸（宽高必须是 16 的倍数） | 1024x1024 |
| `--quality` | 质量 (low/medium/high/auto) | low |
| `--n` | 生成数量 | 1 |
| `--format` | 输出格式 (png/jpeg/webp) | - |
| `--compression` | 压缩率 0-100（仅 jpeg/webp） | - |
| `--background` | 背景 (opaque/auto/transparent) | - |
| `--moderation` | 审核级别 (auto/low) | low |
| `--validate-mask` | 编辑前检查 mask 尺寸/alpha | 否 |
| `--fix-mask-alpha` | mask 无 alpha 时自动转 RGBA（需 Pillow） | 否 |
| `--timeout` | 超时秒数 | 900 |
| `--json` | JSON 输出模式 | 否 |

## 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `IMAGE_API_BASE` | API 端点 | ✅ |
| `IMAGE_API_KEY` | API 密钥 | ✅ |
| `IMAGE_MODEL` | 默认模型 | 否 (默认 gpt-image-2) |
| `IMAGE_OUT_DIR` | 输出目录 | 否 (默认 /tmp/gptimage) |
| `IMAGE_API_MODE` | `auto` / `images` / `responses` | 否 (默认 auto) |

## API 模式

- `images`：保持原始 OpenAI Images API 行为，生成走 `/images/generations`，编辑走 `/images/edits`。
- `responses`：走 `/responses` + `image_generation` tool，适合 freemodel/gpt-5.5 这类只开放 Responses 图片能力的 provider。
- `auto`：如果 `IMAGE_API_MODE=responses` 或 `IMAGE_API_BASE` 以 `/responses` 结尾，自动切到 responses 并规范化 base；否则先尝试 images。如果 `/images/*` endpoint 不存在或返回空图片，再自动切到 responses 重试。

freemodel 示例：

```bash
IMAGE_API_BASE=https://api.freemodel.dev/v1/responses
IMAGE_API_KEY=...
IMAGE_MODEL=gpt-5.5
python3 ~/.hermes/skills/image_api/scripts/image_api.py --json "A cat" --api-mode auto
```

防混用：base 指向 `/responses` 时强制 `--api-mode images` 会直接报错，不会错误拼接 `/responses/images/generations`。

## 分辨率约束

- 最长边 ≤ 3840
- 总像素 655,360 ~ 8,294,400
- 宽高都必须能被 16 整除
- 宽高比 ≤ 3:1
- 竖版实际最大 1920×3840（更大尺寸服务端可能超时）

## 项目结构

```
image_api/
├── README.md
├── SKILL.md              # Agent skill 文档
├── CHANGELOG.md          # 版本变更记录
├── LICENSE
├── .env.example          # 环境变量模板
├── scripts/
│   └── image_api.py      # 核心脚本
└── references/
    ├── fields.md              # 字段映射与交互规范
    ├── provider-quirks.md     # Provider 非标准行为
    ├── resolution-guide.md    # 分辨率约束完整数据
    ├── cpa-provider-quirks.md # CPA 特有行为
    ├── gateway-image-debug.md # 网关图片调试
    └── image-delivery-debugging.md  # 投递问题诊断
```

## License

MIT

## Friend Link

[LinuxDo](https://www.linux.do)
