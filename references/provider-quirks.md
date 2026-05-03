# Provider Quirks — 实测记录

记录各 provider 的非标准行为，供调试参考。

## Edit 模式 MIME type 要求

**问题：** 部分 provider 的 `/v1/images/edits` 端点要求图片以具体 MIME type 上传（如 `image/png`），不接受 `application/octet-stream`。

**错误信息：**
```
Expected a base64-encoded data URL with an image MIME type,
but got unsupported MIME type 'application/octet-stream'
```

**修复（v4.0.0）：** 脚本根据文件扩展名自动检测 MIME type。

## Edit + moderation 组合不稳定

**现象：** `--moderation low` + edit 模式下，部分 provider 有时返回 `stream disconnected` 或 HTTP 502，但重试后通常成功。

**建议：** 脚本自动重试 2 次。仍失败则降级 generate 模式。edit prompt 尽量精简（200 字以内）。

## API Key 错误返回不一致

部分 provider 对过期/错误的 API key 返回 `Upstream request failed` 而非 401/403。排查顺序：
1. 检查 key 长度和前缀
2. 用 `/v1/models` 端点验证 key 有效性
3. 如果 models 能通但 images 不通，是上游服务问题
