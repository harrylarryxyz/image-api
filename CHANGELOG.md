# Changelog

All notable changes to this project will be documented in this file.

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
