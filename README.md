# Image API

通用图片生成与编辑工具，基于 OpenAI Image API (`/v1/images/generations` + `/v1/images/edits`)。

**零依赖**，纯 Python stdlib + curl，不绑死任何 provider。

## 特性

- 🖼️ **文生图** + ✏️ **改图**（支持本地文件/URL/data URL）
- 🔄 **自动重试** — 临时错误（429/502/超时）自动重试 2 次
- 🔀 **主备双端点** — 主端点失败自动切换备用
- 📐 **分辨率验证** — 基于 `resolution_map.json` 的服务端约束验证
- 📊 **JSON 输出** — `--json` 模式输出结构化结果
- 🔍 **双格式支持** — 同时支持 `b64_json` 和 `url` 响应格式（自动检测并下载）
- 🛡️ **内容类型检查** — 检测 HTML 错误页面（网关错误/反爬拦截），给出明确提示
- ⚡ **零依赖** — 只需 Python 3.8+ 和 curl

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API 端点和密钥

# 2. 文生图
source .env
python3 scripts/image_api.py --json "A beautiful sunset" --size 1024x1024 --quality high

# 3. 改图
python3 scripts/image_api.py --json "Make it blue" --edit --image source.png
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
| `--mask` | 遮罩图 | - |
| `--size` | 尺寸 | 1024x1024 |
| `--quality` | 质量 (low/medium/high) | low |
| `--n` | 生成数量 | 1 |
| `--format` | 输出格式 (png/jpeg/webp) | - |
| `--compression` | 压缩率 0-100 | - |
| `--background` | 背景 (opaque/auto/transparent) | - |
| `--moderation` | 审核级别 (auto/low) | low |
| `--timeout` | 超时秒数 | 900 |
| `--json` | JSON 输出模式 | 否 |

## 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `IMAGE_API_BASE` | API 端点 | ✅ |
| `IMAGE_API_KEY` | API 密钥 | ✅ |
| `IMAGE_MODEL` | 默认模型 | 否 (默认 gpt-image-2) |
| `IMAGE_OUT_DIR` | 输出目录 | 否 (默认 /tmp/gptimage) |
| `PRIMARY_IMAGE_API_BASE` | 主端点 URL | 否 |
| `PRIMARY_IMAGE_API_KEY` | 主端点密钥 | 否 |

## 分辨率约束

- 最长边 ≤ 3840
- 总像素 ≤ ~8,000,000
- 宽高都必须能被 16 整除
- 竖版实际最大 1920×3840（更大尺寸服务端可能超时）

## 项目结构

```
image-api/
├── README.md
├── SKILL.md              # Agent skill 文档
├── .env.example          # 环境变量模板
├── scripts/
│   └── image_api.py      # 核心脚本
└── references/
    └── fields.md         # 字段映射与交互规范
```

## License

MIT
