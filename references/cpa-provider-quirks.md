# CPA (CLIProxyAPI) Provider Quirks

**Provider:** CPA Docker container at `api.example.com`
**Model:** gpt-image-2
**Last tested:** 2026-05-03

## Edit Mode MIME Type Requirement

CPA's `/v1/images/edits` endpoint requires images uploaded with specific MIME types (`image/png`, `image/jpeg`, `image/webp`). Generic `application/octet-stream` causes HTTP 400:

```
Invalid 'input[0].content[1].image_url'. Expected a base64-encoded data URL
with an image MIME type (e.g. 'data:image/png;base64,...'),
but got unsupported MIME type 'application/octe...
```

**Fix:** Use file extension to detect MIME type before upload. The `image_api.py` v4.0.0 script handles this automatically via `_guess_mime()`.

## Edit + Moderation Instability

Combining edit mode with `--moderation low` increases the chance of intermittent failures:
- `stream disconnected before completion` (server-side disconnect)
- HTTP 502 with same message

**Pattern observed (v4.0.0 with requests):**
- 3/3 sessions eventually succeeded (retry mechanism works)
- Some sessions need 1-2 retries before succeeding
- Without `--moderation`, edit mode is more reliable (fewer retries needed)

**Behavior before v4.0.0 (curl):**
- Edit + moderation would crash with `NameError` before even reaching the server
- Retry mechanism was never reached

## Generate Mode

Generate mode (`/v1/images/generations`) uses JSON body, not multipart. Generally stable with both `requests` and curl. No special MIME type issues.

## Recommended Parameters

For CyberPersona use case (speed priority):
```
--quality low --format png --moderation low
```

For higher quality (slower):
```
--quality medium --format png --moderation low
```

Timeout: 900s default is sufficient for all sizes up to 1920×3840.
