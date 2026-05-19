# Generic Images API provider quirks

This reference captures generic quirks observed across OpenAI-compatible Images API providers. It is intentionally sanitized: do not record private provider hostnames, personal model routes, account names, or real keys in this public repository.

## Edit mode MIME type requirement

Some `/v1/images/edits` endpoints require image uploads with concrete MIME types such as:

- `image/png`
- `image/jpeg`
- `image/webp`

Generic `application/octet-stream` uploads can trigger errors similar to:

```text
Expected a base64-encoded data URL with an image MIME type,
but got unsupported MIME type 'application/octet-stream'
```

Fix: use file extension and content clues to detect MIME type before upload. The script handles this through `_guess_mime()`.

## Edit + moderation instability

Some providers intermittently fail edit-mode requests when moderation or safety parameters are included. Symptoms may include:

- `stream disconnected before completion`
- HTTP 502 / gateway errors
- transient upstream failures that succeed on retry

Recommended behavior:

- Keep prompts concise.
- Let the script retry transient errors.
- If edits repeatedly fail but generation works, report the provider-specific limitation instead of silently changing user intent.

## Generate mode

Generate mode (`/v1/images/generations`) usually uses a JSON body and is often more stable than multipart edit mode. It should remain separate from edit-mode provider quirks.

## Recommended baseline parameters

For speed-oriented smoke tests:

```bash
--quality low --format png --moderation low
```

For quality-oriented smoke tests:

```bash
--quality medium --format png --moderation low
```

Use provider documentation and live tests before recommending expensive or slow defaults.
