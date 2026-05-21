# Changelog

English | [简体中文](CHANGELOG.zh-CN.md)

All notable changes to this project are documented in this file.

This project follows a human-readable changelog style inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Version numbers are used as project milestones; API-provider behavior may still vary by upstream provider.

## [Unreleased]

### Added

- Professionalized the public README as a provider-agnostic project entry point.
- Expanded documentation for API modes, configuration, CLI parameters, output handling, provider compatibility, security, and testing.
- Added generic provider examples using placeholder hosts and keys instead of real provider credentials.
- `scripts/validate_skill_docs.py` now also checks runtime CLI surfaces, generated cache artifacts, provider-specific hardcoded model defaults, secret-like key placeholders, and the grouped Skill Creator resource structure.

### Changed

- Clarified high-quality chat delivery: send a normal `MEDIA:<path>` preview plus the same image path as a document/file attachment with `[[as_document]]`, not a zip archive.
- Moved provider-specific guidance out of the main README narrative and into `references/` notes.
- Clarified that `IMAGE_API_MODE=auto` is the recommended default for non-expert users.
- Clarified the safe fallback policy: fallback from Images API to Responses API only for missing image endpoints or empty image payloads, not for authentication, quota, validation, content policy, timeout, or generic upstream errors.
- Standardized `SKILL.md` as the authoritative runtime behavior contract with full Hermes skill frontmatter, runtime authority order, verification gates, and provider-agnostic delivery/troubleshooting rules.
- Removed provider-specific built-in model fallback from the CLI; callers must configure `IMAGE_MODEL` or pass `--model` per call.
- Removed provider base URL and model route exposure from JSON/help output surfaces.
- Reorganized `SKILL.md` around Skill Creator progressive disclosure: compact runtime contract, workflow, quick recipes, grouped resource map, troubleshooting escalation, pitfalls, and verification.
- Redacted `IMAGE_MODEL` and explicit one-off model values from user-visible runtime errors.
- Added edit-path model validation before Responses payload construction so programmatic calls cannot send an empty model.
- Renamed the default output directory to `/tmp/image_api` and added a validator guard for stale branded path references.

### Security

- Removed private/local provider naming from the runtime skill surface and replaced public examples with explicit placeholders such as `YOUR_PROVIDER_API_KEY` and `your-image-capable-model`.

## [4.2.0] - 2026-05-20

### Added

- Added Responses API support through `POST /responses` with `tools: [{"type": "image_generation"}]`.
- Added `--api-mode {auto,images,responses}` and matching `IMAGE_API_MODE` environment variable.
- Added automatic API-mode detection:
  - `IMAGE_API_MODE=responses` forces Responses API.
  - `IMAGE_API_BASE` ending in `/responses` selects Responses API and normalizes the base URL internally.
  - default `auto` mode first tries the standard Images API for normal `/v1` bases.
- Added safe fallback from Images API to Responses API when `/images/*` is unavailable or returns no usable image data.
- Added explicit protection against endpoint mixing, such as using an `/responses` base URL with forced `images` mode.
- Added Responses-mode generation and edit support, including primary images, additional reference images, and mask payload construction.
- Added provider-mode reporting in JSON output so automated callers can see whether `images` or `responses` was actually used.
- Added byte-signature image format detection for PNG, JPEG, and WebP to avoid trusting mislabeled provider output.
- Added regression tests for API-mode resolution, Responses payload construction, fallback behavior, and no-fallback authentication errors.
- Added provider-specific reference notes for Responses-style image providers under `references/`.

### Changed

- Default API-mode behavior is now `auto`, making normal `/v1` provider configuration safer for non-expert users.
- JSON output now reports the effective `api_mode` after fallback instead of only the initially resolved mode.
- Responses mode now rejects known-unsupported options before sending requests, including multi-image count requests (`n > 1`) and unsupported transparent-background combinations.
- Documentation now uses the underscore-safe skill identity `image_api` consistently for runtime paths and skill names.

### Fixed

- Fixed incorrect endpoint construction when a configured base URL already included `/responses`.
- Fixed misleading success metadata when auto fallback selected Responses API after an Images API failure.
- Fixed stale hyphenated runtime identity references in docs.
- Fixed edge cases where provider-declared output format did not match returned image bytes.

### Security

- Documented that provider keys belong in local env files such as `~/.hermes/.env` and must not be committed.
- Public README examples now use placeholders rather than real provider-specific keys or private test configuration.

## [4.1.0] - 2026-05-04

### Added

- Multi-reference editing through repeated `--ref` arguments, sent as multipart `image[]` fields where supported.
- Parameter pre-validation for common image constraints: dimensions divisible by 16, longest side limit, total pixel range, and aspect-ratio bounds.
- Mask validation and repair helpers:
  - `--validate-mask` checks dimensions and alpha suitability.
  - `--fix-mask-alpha` converts grayscale masks into RGBA alpha masks when Pillow is available.
- Lazy configuration loading so `--help` and basic argument validation no longer fail when env variables are absent.
- `quality=auto` option.
- `background=transparent` option with provider-specific validation where applicable.
- High-quality delivery guidance for workflows that need both compressed previews and original files.
- Reference documents for provider quirks, gateway image debugging, and image delivery troubleshooting.

### Changed

- Multipart request construction now uses list-of-tuples to support repeated field names.
- MIME detection was promoted to a reusable helper backed by Python's `mimetypes` module.
- Runtime config loading now happens through `ensure_runtime_config()` instead of import-time env reads.

## [4.0.0] - 2026-05-03

### Changed

- Reworked the transport layer from curl subprocess calls to native `requests` calls.
- Replaced `_curl_json` with `_request_json` using `requests.Session.post`.
- Replaced `_curl_multipart` with native `requests` multipart uploads.
- Removed curl-related subprocess/tempfile dependencies from the runtime path.
- Added session-level connection reuse for lower overhead and more stable edit requests.

### Added

- MIME type auto-detection for uploaded images, avoiding generic `application/octet-stream` uploads where providers require concrete types.
- Per-request UUID tracking through `X-Client-Request-Id`.
- More detailed error diagnostics including HTTP status, content type, request id, and gateway metadata where available.

### Fixed

- Fixed edit-mode `NameError: name 'moderation' is not defined` inherited from the earlier curl implementation.
- Fixed provider failures caused by generic upload MIME types.
- Fixed edit-mode retry paths that could fail before retry logic was reached.

## [3.1.0] - 2026-05-01

### Added

- Support for both `b64_json` image responses and URL-based image responses.
- Automatic download of remote image URLs returned by providers.
- Content-type checks to catch HTML gateway/proxy pages before JSON parsing.
- `_download_url()` helper for remote image retrieval.
- `_check_response_headers()` helper for response validation.

### Fixed

- Fixed missing `moderation` parameter propagation in edit mode.

## [3.0.0] - 2026-04-30

### Changed

- Moved to environment-variable-driven configuration.
- Removed hard-coded dependence on a single provider.
- Added support for primary/backup endpoint patterns where configured.

### Added

- Retry mechanism for transient failures such as 429, 502, 503, 504, and timeouts.
- Structured `--json` output mode.
- URL and data URL support for image inputs.
- Documented resolution constraints based on observed provider behavior.

## [2.0.0] - 2026-04-29

### Added

- Image editing through `POST /images/edits`.
- Local file, URL, and data URL input support.
- Mask support for edit workflows.

## [1.0.0] - 2026-04-28

### Added

- Initial text-to-image generation through `POST /images/generations`.
- Basic CLI parameters.
- Environment-variable configuration.
