# Changelog

All notable changes to this project will be documented in this file.

## [4.0.0] - 2026-05-03

### Changed
- **架构重构**: curl 子进程 → requests 原生调用，提升 edit 模式稳定性
- `_curl_json` → `_request_json` (使用 `requests.Session.post`)
- `_curl_multipart` → `_request_multipart` (使用 `requests` 原生 `files=` 参数)
- 移除 `subprocess`、`tempfile`（curl 相关）依赖
- 使用 `requests.Session` 复用连接，减少进程开销

### Added
- **MIME type 自动检测**: 根据文件扩展名上传 `image/png`、`image/jpeg` 等具体类型，不再使用 `application/octet-stream`
- **请求追踪**: 每个请求生成 UUID，通过 `X-Client-Request-Id` 头传递
- **详细错误诊断**: 错误信息包含 HTTP 状态码、Content-Type、Request-ID、CF-Ray
- **连接复用**: Session 级别复用 HTTP 连接

### Fixed
- 修复 edit 模式 `NameError: name 'moderation' is not defined`（v3.x curl 架构遗留 bug）
- 修复部分 provider 拒绝 `application/octet-stream` MIME type 的问题
- 修复 edit 模式重试机制实际不生效的问题（旧版崩溃在重试逻辑之前）

## [3.1.0] - 2026-05-01

### Added
- **双格式支持**: 同时支持 `b64_json` 和 `url` 响应格式，自动检测并下载远程图片
- **内容类型检查**: 检测 HTML 错误页面（网关错误/反爬拦截），给出明确错误提示而非 `JSON decode failed`
- 新增 `_download_url()` 函数用于远程图片下载
- 新增 `_check_response_headers()` 函数用于 content-type 验证

### Fixed
- 修复改图模式未传递 `moderation` 参数的问题

## [3.0.0] - 2026-04-30

### Changed
- 重构为纯环境变量驱动，不再读取 config.yaml
- 移除对特定 provider 的硬编码依赖
- 支持主备双端点自动切换

### Added
- 自动重试机制（429/502/503/504/timeout 最多重试 2 次）
- `--json` 结构化输出模式
- 支持 URL 和 data URL 作为图片来源
- 分辨率约束实测数据

## [2.0.0] - 2026-04-29

### Added
- 改图功能（`/v1/images/edits` 端点）
- 支持本地文件、URL、data URL 三种图片来源
- mask 支持

## [1.0.0] - 2026-04-28

### Added
- 初始版本
- 文生图功能（`/v1/images/generations` 端点）
- CLI 参数支持
- 环境变量配置
