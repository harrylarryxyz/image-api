---
name: image-api
description: Generate and edit images using Image API. Generic wrapper that works with any OpenAI-compatible image provider. Handles auth via env vars, retry on transient failures, resolution constraints, prompt verbatim passing, and content moderation.
version: 4.0.1
---

# Image API

使用 Image API 生成或编辑图片。不绑定任何 provider，通过环境变量配置。

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
python3 ~/.hermes/skills/image-api/scripts/image_api.py --json "<prompt>" --size <size> --quality low --format png --moderation low
```

**改图：**
```bash
source ~/.hermes/.env && export IMAGE_API_KEY IMAGE_API_BASE
python3 ~/.hermes/skills/image-api/scripts/image_api.py --json --edit --image "<path>" "<prompt>" --size <size> --quality low --format png --moderation low
```

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

## 关键陷阱

1. **terminal cwd 被删除** — 清理临时目录前先 `cd /root`，否则后续所有 terminal 调用报 FileNotFoundError。已坏时用 `execute_code + subprocess.run(cwd="/root")` 绕过
2. **API Key 无效返回 "Upstream request failed"** — 某 provider 对错误 key 不返回 401 而是 upstream failed，先验证 key 再重试
3. **edit 模式 stream disconnected** — 部分 provider 不稳定，脚本自动重试 2 次。仍失败则降级 generate
4. **分辨率上限** — 竖版最大 1920×3840，超过会服务端超时

## 详细参考

- `references/fields.md` — 字段映射、安全替换表
- `references/provider-quirks.md` — Provider 非标准行为
- `references/resolution-guide.md` — 分辨率约束完整数据
