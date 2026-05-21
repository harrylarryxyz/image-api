# 字段与交互规则

本文件是 `image_api` 的字段映射参考。`SKILL.md` 仍是 runtime 行为权威；若两者冲突，以 `SKILL.md` 为准。

## 任务类型

- 文生图：调用 Images-style `/images/generations` 或 Responses-style `/responses`。
- 改图/参考图：调用 Images-style `/images/edits` 或 Responses-style `/responses`。

如果用户表达包含明确的图片来源（本地路径、URL、data URL、当前会话附件）且语义是“修改图片 / 编辑图片 / 改图 / 以此为参考”，优先识别为改图/参考图工作流。

## 必填字段

### 文生图

- `prompt`
- `model`：来自 `IMAGE_MODEL` 或单次 `--model <provider-specific-image-model>`

如果缺少 `prompt`，先向用户追问，不要执行脚本：

```text
请补充图片提示词，例如你想生成什么画面。
```

如果缺少模型配置，先提示配置本地 `IMAGE_MODEL` 或在单次调用中传 `--model`；不要在公共回复中推荐私有模型路由。

### 改图/参考图

- `prompt`
- 主图来源：本地路径、URL、data URL 或当前会话附件导出的本地文件
- `model`：来自 `IMAGE_MODEL` 或单次 `--model <provider-specific-image-model>`

如果缺少图片来源，提示用户提供来源：

```text
请提供要编辑的图片来源：本地路径、图片 URL、data URL，或重新发送图片附件。
```

如果缺少修改要求，向用户追问：

```text
请补充修改要求，例如你想把图片改成什么效果。
```

## 多参考图编辑

使用 repeatable `--ref` 传入额外参考图：

```bash
python3 image_api.py --json --edit --image <主图> --ref <参考1> --ref <参考2> "<prompt>"
```

- `--image`：主图（必须），通常是要保留主体/人物/物体的图。
- `--ref`：额外参考图（可选，可重复），通常是场景、风格、调色板或素材。
- `--mask`：遮罩图（可选），用于局部编辑。

底层字段会按 API mode 选择兼容形态；不要在 agent 回复中暴露 provider 私有 endpoint。

## 可选字段

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `model` | `IMAGE_MODEL` 或 `--model` | provider-specific 模型名称；公共文档只写占位说明 |
| `size` | `1024x1024` | 图片尺寸（宽高通常必须是 16 的倍数） |
| `quality` | `low` | `low` / `medium` / `high` / `auto` |
| `background` | - | `opaque` / `auto` / `transparent`；provider/model 不支持时报告限制 |
| `output_format` | `png` | `png` / `jpeg` / `webp`；保存后以 magic header 验证实际格式 |
| `output_compression` | - | 压缩率 0-100（仅 `jpeg`/`webp`） |
| `n` | `1` | 请求数量；部分 provider/API mode 可能只返回 1，需要多张时可循环请求 |
| `moderation` | `low` | `auto` / `low`；不代表无过滤 |
| `response_format` | `b64_json` | 响应格式；agent 应使用 `--json` 并验证本地文件 |
| `mask` | - | 改图时的 mask 图（本地路径/URL/data URL） |
| `ref` | - | 额外参考图（可重复传入） |

## 自然语言映射

### size

| 用户说法 | API 参数 | 备注 |
|---------|---------|------|
| 1024x1024 / 1:1 | `size=1024x1024` | 正方形，最安全 |
| 1024x1536 / 3:4 | `size=1024x1536` | 竖版标准 |
| 1536x1024 / 4:3 | `size=1536x1024` | 横版标准 |
| 1536x2048 | `size=1536x2048` | 竖版大图 |
| 1792x2560 | `size=1792x2560` | 竖版高清 |
| 1920x3840 | `size=1920x3840` | 高竖版，较易触发超时 |
| 2048x2048 | `size=2048x2048` | 2K 正方形 |
| 2048x3072 | `size=2048x3072` | 竖版高清 |
| 3840x2160 / 16:9 / 4K 横向 | `size=3840x2160` | 4K 横向 |
| auto | `size=auto` | 交给 provider 决定 |

大尺寸与长 prompt 组合更容易触发超时或断流。生成接近上限的尺寸时，优先简化 prompt，并在失败时报告 provider 限制，不要静默改任务语义。

### quality

| 用户说法 | API 参数 |
|---------|---------|
| 高清 / 高质量 / 高品质 | `quality=high` |
| 中等质量 | `quality=medium` |
| 低质量 / 快速 | `quality=low` |
| 自动 / auto | `quality=auto` |

### background

| 用户说法 | API 参数 |
|---------|---------|
| 透明背景 | `background=transparent` |
| 自动背景 | `background=auto` |
| 不透明背景 | `background=opaque` |

部分 provider/model 组合不支持 `transparent`。失败时报告限制，不要擅自删除用户的透明背景要求。

### output_format

| 用户说法 | API 参数 |
|---------|---------|
| png | `output_format=png` |
| jpg / jpeg | `output_format=jpeg` |
| webp | `output_format=webp` |

### n

| 用户说法 | API 参数 |
|---------|---------|
| 生成 3 张 / 来 3 张 / 输出 3 张 | `n=3`；若 API mode 不支持多张，则循环请求 |
| 未指定 | `n=1` |

## timeout 规则

脚本默认超时为 **900 秒**（15 分钟），适用于大多数场景。

如果用户明确要求极端大图或多图，可显式增加：

```bash
--timeout 1200
```

判断建议：

1. 读取已提取的 `size`。
2. 如果 `size` 匹配 `^\d+x\d+$`，拆出宽高并计算总像素量。
3. 若总像素量接近上限或 prompt 很长，考虑 `--timeout 1200`。
4. 否则使用脚本默认 900 秒。

## 字段优先级

1. 用户明确写出的字段值。
2. 用户自然语言中的明确要求。
3. 本 skill 的快速基线与脚本默认值。
4. provider 限制只用于报错/解释，不得静默覆盖用户意图。

## 成功输出格式

脚本 `--json` 成功输出包含：

```json
{
  "ok": true,
  "paths": ["<local-output-path>"],
  "used_params": {
    "mode": "generate",
    "size": "1024x1024",
    "quality": "low",
    "output_format": "png",
    "n": 1,
    "moderation": "low",
    "api_mode": "images"
  }
}
```

agent 对用户的最终回复只应交付图片/文件与简短说明；不要粘贴真实本地路径、provider base URL、API key 或私有模型路由。

## 失败输出格式

```text
生成失败: <简短错误原因>
```

若错误涉及鉴权、额度、schema、内容安全、超时或 upstream failure，保留真实错误类别，但脱敏 base URL、key、模型私有路由。

## 内容安全与 prompt 处理

`moderation=low` 不代表无过滤。默认规则是 **prompt 原样直传**：不翻译、不润色、不扩写、不自动替换敏感词。

如果 provider 拒绝内容：

1. 向用户说明被拒绝/受限的错误类别。
2. 询问用户是否要改写为更安全的表达。
3. 只有在用户同意优化 prompt 时，才提供替代表达。

不要自行把用户要求替换成另一种语义；这会违反 `SKILL.md` 的 prompt pass-through contract。
