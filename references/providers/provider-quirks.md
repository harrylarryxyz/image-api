# Provider Quirks — Generic Debug Notes

记录 provider 的非标准行为时保持 provider-agnostic：不要写真实 provider 名称、私有 base URL、真实 key、私有模型路由或用户任务数据。

## Edit 模式 MIME type 要求

**问题：** 部分 provider 的 image-edit endpoint 要求图片以具体 MIME type 上传（如 `image/png`），不接受 `application/octet-stream`。

**典型错误：**
```text
Expected a base64-encoded data URL with an image MIME type,
but got unsupported MIME type 'application/octet-stream'
```

**处理：** 脚本根据文件扩展名自动检测 MIME type。若仍失败，报告 MIME/文件格式限制，不要把编辑任务静默改成文生图。

## Edit + moderation 组合不稳定

**现象：** `--moderation low` + edit 模式下，某些 provider 可能返回 `stream disconnected`、HTTP 502/503/504 或 generic upstream error。

**处理：** 脚本可按 retry policy 重试短暂故障。重试后仍失败时，向用户报告 provider/endpoint 限制或建议降低尺寸、简化 prompt；不要降级为 generate 模式，因为这会改变“编辑原图”的用户意图。

## API key 错误返回不一致

部分 provider 会把过期/错误 key 表达为 generic upstream error，而不是标准 401/403。排查顺序：

1. 确认本地 secret store/env 中的 key 是否存在且未过期。
2. 用 provider 支持的模型/账户探针端点验证 key 与模型可见性。
3. 若 key 与模型可见但图片 endpoint 不通，按 endpoint/API-mode 问题排查。
4. 不要在公共 issue、README、SKILL.md 或聊天回复中粘贴真实 key、base URL 或模型路由。

## Model-specific notes

- [OpenAI image model notes](openai-image-models.md) documents GPT Image 2 constraints, transparent-background handling, timeout hints, and smoke-test coverage.
