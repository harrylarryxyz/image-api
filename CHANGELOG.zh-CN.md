# 更新日志

[English](CHANGELOG.md) | 简体中文

本文件记录项目的重要变更。

本项目使用接近 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 的人类可读结构。版本号用于标识项目里程碑；具体 API-provider 行为仍可能随上游 provider 而变化。

## [Unreleased]

### Added

- 将公开 README 专业化为 provider-agnostic 的项目入口文档。
- 扩展了 API 模式、配置、CLI 参数、输出处理、provider 兼容性、安全和测试说明。
- 文档示例统一使用占位 host 和占位 key，避免出现真实 provider 凭据或私人测试配置。
- 新增中文 README 与中文 CHANGELOG，并在中英文文档顶部加入语言互链。

### Changed

- 将 provider-specific 说明从 README 主叙事移到 `references/` 笔记中。
- 明确 `IMAGE_API_MODE=auto` 是非专家用户的推荐默认值。
- 明确安全 fallback 策略：只有 Images API 端点缺失或图片 payload 为空时，才从 Images API fallback 到 Responses API；不会因鉴权、额度、参数校验、内容安全、超时或通用上游错误而 fallback。
- 清理公开 reference 与 `SKILL.md` 中的个人 provider、模型路线和私有环境痕迹，保留泛化后的兼容性经验。

## [4.2.0] - 2026-05-20

### Added

- 新增 Responses API 支持：通过 `POST /responses` 和 `tools: [{"type": "image_generation"}]` 生成图片。
- 新增 `--api-mode {auto,images,responses}` 以及对应环境变量 `IMAGE_API_MODE`。
- 新增 API 模式自动检测：
  - `IMAGE_API_MODE=responses` 强制使用 Responses API。
  - `IMAGE_API_BASE` 以 `/responses` 结尾时选择 Responses API，并在内部规范化 base URL。
  - 默认 `auto` 模式会先对普通 `/v1` base 尝试标准 Images API。
- 当 `/images/*` 不可用或没有返回可用图片数据时，安全 fallback 到 Responses API。
- 对端点混用做显式保护，例如 `/responses` base URL 搭配强制 `images` 模式时直接报错。
- 新增 Responses 模式的生成和编辑支持，包括主图片、额外参考图和 mask payload 构造。
- JSON 输出新增实际 provider mode 报告，自动化调用方可以看到实际使用的是 `images` 还是 `responses`。
- 新增 PNG、JPEG、WebP 的字节签名检测，避免信任 provider 标错的输出格式。
- 新增 API 模式解析、Responses payload 构造、fallback 行为、鉴权错误不 fallback 等回归测试。
- 在 `references/` 下新增 Responses-style image provider 的兼容性参考。

### Changed

- 默认 API 模式改为 `auto`，让普通 `/v1` provider 配置对非专家用户更安全。
- JSON 输出现在报告 fallback 后的实际 `api_mode`，而不是只报告最初解析出的模式。
- Responses 模式会在发送请求前拒绝已知不支持的选项，例如多图数量请求 (`n > 1`) 和不稳定的透明背景组合。
- 文档统一使用 underscore-safe 的 skill identity：`image_api`。

### Fixed

- 修复配置 base URL 已包含 `/responses` 时 endpoint 拼接错误的问题。
- 修复 auto fallback 选择 Responses API 后成功 metadata 仍误导的问题。
- 修复文档中残留的 hyphenated runtime identity。
- 修复 provider 声明输出格式与实际图片字节不一致时的保存扩展名问题。

### Security

- 明确 provider key 应保存在本地 env 文件，例如 `~/.hermes/.env`，不能提交到仓库。
- README 公开示例改用占位符，不再出现真实 provider-specific key 或私人测试配置。

## [4.1.0] - 2026-05-04

### Added

- 新增多参考图编辑：可重复传入 `--ref`，在支持的 provider 上以 multipart `image[]` 字段发送。
- 新增常见图片约束预校验：尺寸可被 16 整除、最长边限制、总像素范围、宽高比限制。
- 新增 mask 校验与修复：
  - `--validate-mask` 检查尺寸和 alpha 是否适合。
  - `--fix-mask-alpha` 在 Pillow 可用时把灰度 mask 转成 RGBA alpha mask。
- 延迟配置加载：`--help` 和基础参数校验不再因缺少环境变量而失败。
- 新增 `quality=auto` 选项。
- 新增 `background=transparent` 选项，并在适用时进行 provider-specific 校验。
- 增加高质量投递建议，适合需要同时提供压缩预览和原始文件的工作流。
- 新增 provider quirks、gateway image debugging、image delivery troubleshooting 等参考文档。

### Changed

- Multipart 请求构造改为 list-of-tuples，以支持重复字段名。
- MIME 检测提升为复用 helper，并基于 Python `mimetypes` 标准库。
- 运行时配置改为通过 `ensure_runtime_config()` 加载，不再在 import 时读取 env。

## [4.0.0] - 2026-05-03

### Changed

- 传输层从 curl 子进程调用重构为原生 `requests` 调用。
- `_curl_json` 替换为使用 `requests.Session.post` 的 `_request_json`。
- `_curl_multipart` 替换为原生 `requests` multipart 上传。
- 从运行路径中移除 curl 相关的 subprocess/tempfile 依赖。
- 新增 session 级连接复用，降低开销并提升 edit 请求稳定性。

### Added

- 上传图片 MIME type 自动检测，避免 provider 要求具体 MIME 时收到 `application/octet-stream`。
- 通过 `X-Client-Request-Id` 传递每请求 UUID。
- 更详细的错误诊断，包括 HTTP 状态、content type、request id 和可用的 gateway metadata。

### Fixed

- 修复早期 curl 实现遗留的 edit 模式 `NameError: name 'moderation' is not defined`。
- 修复部分 provider 因通用上传 MIME type 而失败的问题。
- 修复 edit 模式在进入重试逻辑前就失败的路径。

## [3.1.0] - 2026-05-01

### Added

- 同时支持 `b64_json` 图片响应和 URL 图片响应。
- 自动下载 provider 返回的远程图片 URL。
- 新增 content-type 检查，在 JSON 解析前捕获 HTML gateway/proxy 页面。
- 新增 `_download_url()` helper 用于远程图片获取。
- 新增 `_check_response_headers()` helper 用于响应校验。

### Fixed

- 修复 edit 模式没有传递 `moderation` 参数的问题。

## [3.0.0] - 2026-04-30

### Changed

- 改为环境变量驱动配置。
- 移除对单一 provider 的硬编码依赖。
- 在已配置场景下支持主/备 endpoint 模式。

### Added

- 新增临时失败重试机制，例如 429、502、503、504 和超时。
- 新增结构化 `--json` 输出模式。
- 图片输入支持 URL 和 data URL。
- 文档化基于实测 provider 行为的分辨率约束。

## [2.0.0] - 2026-04-29

### Added

- 通过 `POST /images/edits` 支持图片编辑。
- 支持本地文件、URL 和 data URL 输入。
- 支持 mask 编辑工作流。

## [1.0.0] - 2026-04-28

### Added

- 通过 `POST /images/generations` 支持初始文生图。
- 基础 CLI 参数。
- 环境变量配置。
