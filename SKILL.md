---
name: image-api
description: Generate and edit images using Image API. Generic wrapper that works with any OpenAI-compatible image provider. Handles auth via env vars, retry on transient failures, resolution constraints, prompt verbatim passing, and content moderation.
version: 3.0.2
---

# Image API

使用 Image API 的 `/v1/images/generations` 和 `/v1/images/edits` 端点生成和编辑图片。

**通用设计：** 不绑定任何具体 provider，通过环境变量配置 API 端点和密钥，支持任意 OpenAI 兼容的图片生成服务。

> **设计原则：** 所有配置通过环境变量获取，用户可以自由切换 provider 而无需修改脚本。脚本支持主备双端点自动切换。

## 目标

- 识别用户是要文生图还是改图
- 从用户自然语言中提取可用字段
- 缺少关键字段时先追问用户，不要盲目执行
- 字段足够时调用 `scripts/image_api.py`
- 完成后向用户输出图片路径和实际使用的关键参数

## 何时使用

用户要求生成或编辑图片，且没有提到"对话""多轮""streaming" 等其他 API 关键词时，默认使用本 skill。

## 资源文件

- `scripts/image_api.py` — 生产级 Python wrapper（CLI + 程序化 API + JSON 输出）
- `references/fields.md` — 字段映射、timeout 规则、交互规范、安全替换表

## 环境配置

### 方式一：单端点（简单模式）

只需要设置一个端点：

| 环境变量 | 说明 | 示例 |
|---------|------|------|
| `IMAGE_API_BASE` | API 端点（不带尾部斜杠） | `https://your-provider.com/v1` |
| `IMAGE_API_KEY` | API 密钥 | `sk-xxx...` |

**可选环境变量：**

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `IMAGE_OUT_DIR` | 输出目录 | `/tmp/gptimage` |
| `IMAGE_MODEL` | 默认模型名 | `gpt-image-2` |

### 方式二：主备双端点（高可用模式）

设置主备两个端点，主端点失败时自动切换到备用端点：

| 环境变量 | 说明 |
|---------|------|
| `PRIMARY_IMAGE_API_BASE` | 主端点 URL |
| `PRIMARY_IMAGE_API_KEY` | 主端点密钥 |
| `IMAGE_API_BASE` | 备用端点 URL（主端点失败时使用） |
| `IMAGE_API_KEY` | 备用端点密钥 |

**配置方式：** 在 `.env` 中添加：
```
# 单端点模式
IMAGE_API_BASE=https://your-provider-endpoint/v1
IMAGE_API_KEY=your-api-key

# 或者主备双端点模式
PRIMARY_IMAGE_API_BASE=http://localhost:8080/v1
PRIMARY_IMAGE_API_KEY=your-primary-key
IMAGE_API_BASE=https://your-remote-provider.com/v1
IMAGE_API_KEY=your-backup-key
```

**优先级：**
1. 命令行 `--base-url` + `--api-key`（最高优先级）
2. 环境变量 `PRIMARY_IMAGE_API_BASE` + `PRIMARY_IMAGE_API_KEY`（主端点）
3. 环境变量 `IMAGE_API_BASE` + `IMAGE_API_KEY`（备用端点/单端点模式）
4. 配置文件（最后回退）

## 任务分类

先判断任务类型：

### 文生图
出现这类意图时，按文生图处理：
- `生成图片`
- `文生图`
- `画一张图`
- `用 gpt-image-2 生成`

### 改图
出现这类意图时，按改图处理：
- `修改图片`
- `编辑图片`
- `改图`
- `把这张图改成...`

如果同时出现图片来源（本地路径、URL、data URL）和修改意图，优先按改图处理。

## 字段提取规则

先参考 `references/fields.md` 的规则提取字段。

### 必填字段

#### 文生图
- `prompt`

如果缺少 `prompt`，先向用户追问：
```
请补充图片提示词，例如你想生成什么画面。
```

#### 改图
- `prompt`
- 图片来源（本地路径 / URL / data URL）

如果缺少图片来源，向用户明确提示二选一：
```
请提供要编辑的图片来源：1）本地路径 2）图片 URL / data URL
```

如果缺少修改要求，向用户追问：
```
请补充修改要求，例如你想把图片改成什么效果。
```

### 可选字段

如果用户自然语言中包含以下信息，尽量提取并传给脚本：
- `size`
- `quality`
- `background`
- `output_format`
- `n`
- `moderation`
- `output_compression`
- `mask`（改图）

如果用户没有提供，不要为可选字段反复追问，直接用默认值。

### 自然语言映射（快速参考）

优先识别这些自然语言：
- `高清` → `quality=high`
- `透明背景` → `background=transparent`
- `1024x1024` / `1:1` → `size=1024x1024`
- `1024x1536` / `3:4` → `size=1024x1536`
- `1536x1024` / `4:3` → `size=1536x1024`
- `2048x2048` → `size=2048x2048`
- `3840x2160` / `16:9` / `4k横向` → `size=3840x2160`
- `2160x3840` / `9:16` / `4k竖向` → `size=2160x3840`
- `auto` → `size=auto`
- `png` / `jpg` / `jpeg` / `webp` → `output_format=...`
- `生成3张` → `n=3`

如果用户明确要求保存格式，按用户要求保存；否则默认保存为 `png`。

## 执行步骤

### 1. 整理参数

从用户消息中整理出：
- `mode`: `generate` 或 `edit`
- `prompt`
- `image`（改图时：本地路径 / URL / data URL）
- `mask`（如果用户明确提供）
- 其他可选字段

### 2. 缺字段就停下来问

缺少必填字段时，不要调用脚本。

### 3. 计算 timeout

脚本默认超时为 **900 秒**（15 分钟），适用于所有场景。通常不需要手动调整。

### 4. 调用脚本

使用 Bash 调用 Python 脚本。脚本路径：`scripts/image_api.py`

**必须加上 `--json` 标志**，使脚本输出结构化 JSON，便于 agent 解析。

#### 文生图调用示例
```bash
python3 scripts/image_api.py --json "<原样直传的 prompt>" --size <size> --quality <quality>
```

#### 改图调用示例
```bash
python3 scripts/image_api.py --json "<指令>" --edit --image "<image>" --size <size>
```

根据已提取到的字段，继续附加参数：
- `--size`
- `--quality`
- `--background`
- `--format`
- `--n`
- `--moderation`
- `--compression`
- `--mask`

### 5. 脚本行为

`scripts/image_api.py` 会：
- 从环境变量读取配置（支持主备双端点自动切换）
- 使用 `Authorization: Bearer <key>` 调用接口
- 文生图走 `/v1/images/generations`
- 改图走 `/v1/images/edits`
- 改图支持本地路径、URL、data URL 三种图片来源
- **自动重试：** 对临时性错误（upstream failed, 429, 502-504, timeout）最多重试 2 次，间隔 5 秒
- **主备切换：** 主端点失败时自动切换到备用端点
- 将返回图片保存到 `/tmp/gptimage/`
- `--json` 模式下输出结构化 JSON

## 结果处理

脚本 `--json` 模式成功时会输出 JSON：
```json
{"ok": true, "paths": ["/tmp/gptimage/xxx.png"], "used_params": {"model": "gpt-image-2", "size": "1024x1024", "quality": "high", "n": 1}, "endpoint": "https://..."}
```

脚本 `--json` 模式失败时会输出 JSON：
```json
{"ok": false, "error": "生成失败: ...", "endpoint": "https://..."}
```

### 成功回复格式

向用户输出：
- `图片已生成, 图片路径: <路径>`
- `实际使用的关键参数: model=..., size=..., quality=..., n=...`

如果生成多张图片，列出所有路径。

### 失败回复格式

向用户输出：
- `生成失败: <简短错误原因>`

## 分辨率约束（实测）

| 约束 | 值 | 错误信息 |
|------|-----|---------|
| 最长边 | ≤ 3840 | `The longest edge must be ≤ 3840` |
| 总像素 | ≈ ≤ 8,000,000 | `Requested resolution exceeds...` |
| 可被 16 整除 | W 和 H 都必须 | `Width and height must both be divisible by 16` |
| 实际服务端超时上限 | 竖版 ≤ 1920×3840 | `stream disconnected before completion` |

**验证通过的尺寸：** `3840x1920`, `3840x2048`, `3840x1536`, `2560x2560`, `2048x2048`, `1920x3840`, `2048x3072`, `2048x3584`

**已知失败的尺寸：** `3840x3840`, `3840x2560`, `3072x3072`, `4096x2048`, `2048x3840`, `2160x3840`

> 注意：2048×3840 和 2160×3840 虽然满足最长边 ≤ 3840 和总像素 < 8,000,000 的硬性约束，但实际会因服务端处理超时而失败。竖版实际可用最大尺寸为 **1920×3840**。

## Prompt 处理规则

**必须原样直传用户的 prompt，不做任何修改或翻译。**
仅在用户明确要求时才优化或扩展。

gpt-image-2 支持多语言输入，中文 prompt 可以正常工作。

## 质量选择

| Quality | 用途 | 细节 |
|---------|------|------|
| `low` | 快速草稿 | 最低细节，最快 |
| `medium` | 一般用途 | 用户反馈某些场景可能偏模糊 |
| `high` | 专业海报、精细场景 | 最清晰，文字可读性最好 |

**默认 quality 为 `low`，用户未指定时不追问。**
若用户抱怨图片模糊或缺少细节，建议重新生成并指定 `quality=high`。

## 内容审核

- `moderation` 固定传 `"low"`（用户强制要求）
- `"low"` 不代表无过滤，某些敏感组合仍会触发 hard block
- 见 `references/fields.md` 中的安全替换表

## 重试机制

脚本内置自动重试，对以下临时性错误最多重试 2 次，间隔 5 秒：

- `Upstream request failed`
- `stream disconnected`
- HTTP 429（限流）
- HTTP 502/503/504（服务端临时错误）
- `timeout` / `connection reset`

JSON 输出中，成功时会显示实际尝试次数。

## 长时间处理

| Size | 典型耗时 | 默认超时是否够用 |
|------|---------|---------|
| ≤2048×2048 | 15–30s | ✅ 默认 900s 足够 |
| 3840×1920/2048 | 60–120s | ✅ 默认 900s 足够 |
| 竖版 1920×3840 | 120–180s | ✅ 默认 900s 足够 |

## 故障诊断

### 症状：`IMAGE_API_BASE 未设置` 或 `IMAGE_API_KEY 未设置`

**原因：** 环境变量未配置
**解决：** 在 `.env` 中添加：
```
IMAGE_API_BASE=https://your-provider/v1
IMAGE_API_KEY=your-key
```

### 症状：返回 `data_count: 0` 或无图片

**原因：** 上游过滤拒绝生成
**解决：** 简化 prompt，移除敏感描述，或尝试不同尺寸

### 症状：`stream disconnected before completion`

**原因1：** prompt 过长 + 尺寸过大组合触发超时
**原因2：** 敏感描述组合（即使 moderation=low）
**解决：**
- 精简 prompt 至 200 字以内
- 降低尺寸（竖版最大建议 1920×3840）
- 使用 `references/fields.md` 中的安全替换表改写 prompt
- 脚本会自动重试 2 次

### 症状：`Upstream request failed`（重试后仍失败）

**原因1：** 上游服务持续不可用
**原因2（常见）：** API Key 错误或过期。某些 provider 对无效 key 也返回 "Upstream request failed" 而非 401，容易误判为上游问题。

**排查顺序：**
1. 先验证 key 是否正确：
```bash
echo "Key length: ${#IMAGE_API_KEY}, prefix: ${IMAGE_API_KEY:0:8}"
```
2. 用 models 端点验证 key 有效性：
```bash
curl -s -H "Authorization: Bearer $IMAGE_API_KEY" "$IMAGE_API_BASE/models" | head -c 200
```
如果返回模型列表 → key 有效，是图片服务临时问题。如果返回 auth error → key 有问题。
3. 检查 API 端点是否正确（必须带 `/v1` 后缀）

### 症状：脚本调用失败或返回异常

**原因：** `image_api.py` 脚本执行出错
**检查：**
```bash
python3 scripts/image_api.py --json "test" --size 1024x1024
```
**解决：**
- 检查脚本路径是否存在
- 检查 Python 环境：`python3 --version`
- 查看具体错误信息

## Edits API 限制与替代方案

### 多张参考图限制（重要）

edits API (`/v1/images/edits`) **一次只能处理一张基础图 (`--image`) + 一张可选的 mask (`--mask`)**。mask 是黑白遮罩，不能作为风格/场景参考图使用。

遇到"用A图的风格改B图"类需求时：
1. 明确告知限制
2. 请用户文字描述参考图特征
3. 以主体图作为 `--image`，将描述写进 prompt

### 输入约束
- **One base image** (`image`): the image to be edited. Must be PNG.
- **One optional mask** (`mask`): single-channel, white = regenerate, black/transparent = keep original.
- **Prompt**: passed verbatim.
- **Model**: `gpt-image-2` (or configured via `IMAGE_MODEL`)
- **n**: always `1` (server-side limit)

## 注意事项

- 不要在缺少必填字段时猜测用户意图
- 不要为可选字段做冗长说明
- 改图时，本地路径、URL、data URL 都要支持
- 除非用户明确要求，不要增加接口里没有的自定义字段
- 调用完成后，优先返回结果，不要输出多余解释
