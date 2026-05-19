# Responses-only provider compatibility notes

Use this reference when adapting `image_api` to a provider that exposes image generation through an OpenAI-compatible Responses API shape instead of the classic Images API endpoints.

This document intentionally uses sanitized placeholders. Do not record real provider hostnames, private account URLs, API keys, or personal model-routing details in the public repository. If a concrete provider must be documented, use a private note outside the repo or a sanitized adapter profile.

## Provider shape

Some providers support image generation through:

```text
POST https://api.example.com/v1/responses
model: your-image-capable-model
tools: [{"type": "image_generation"}]
```

They may not support classic Images API endpoints:

```text
/v1/images/generations
/v1/images/edits
```

Recommended public configuration pattern:

```bash
IMAGE_API_BASE=https://api.example.com/v1
IMAGE_API_KEY=sk-your-provider-key
IMAGE_MODEL=your-image-capable-model
IMAGE_API_MODE=auto
```

If a provider requires users to include the endpoint path explicitly, this is also supported:

```bash
IMAGE_API_BASE=https://api.example.com/v1/responses
IMAGE_API_KEY=sk-your-provider-key
IMAGE_MODEL=your-image-capable-model
IMAGE_API_MODE=auto
```

With `auto`, `image_api` first tries Images API for a normal `/v1` base, then falls back to `/responses` only when the Images endpoint is missing or returns no image data. It does not fallback on auth, quota, moderation, schema, timeout, or generic upstream errors.

When `IMAGE_API_BASE` ends in `/responses`, `image_api` should normalize the base to `/v1` and use `/responses` exactly once. Do not append Images API paths to a `/responses` base.

## Confirmed payload shapes

### Text-to-image

```json
{
  "model": "your-image-capable-model",
  "input": "Generate a simple icon on a white background.",
  "tools": [
    {
      "type": "image_generation",
      "size": "1024x1024",
      "output_format": "png"
    }
  ]
}
```

The returned image is expected in `output[].result` for entries with `type: "image_generation_call"`.

### Single-image edit

```json
{
  "model": "your-image-capable-model",
  "input": [
    {
      "role": "user",
      "content": [
        {"type": "input_text", "text": "Change the icon color to blue."},
        {"type": "input_image", "image_url": "data:image/png;base64,..."}
      ]
    }
  ],
  "tools": [{"type": "image_generation"}]
}
```

### Multi-reference edit

Pass multiple `input_image` content items after the text prompt. Treat this as provider-dependent and cover it with a live smoke test before documenting support.

### Mask edit

Common working shape:

```json
{
  "tools": [
    {
      "type": "image_generation",
      "input_image_mask": {
        "image_url": "data:image/png;base64,..."
      }
    }
  ]
}
```

Avoid passing `input_image_mask` as a bare string, and avoid including `type: "input_image"` inside the mask object unless a provider explicitly documents that shape.

## Compatibility matrix template

Use this sanitized template when adding a provider note:

- `size`: works / partial / unsupported.
- `output_format: png`: works / partial / unsupported.
- `output_format: jpeg`: works / partial / unsupported.
- `output_format: webp`: works / may return another byte format / unsupported.
- `output_compression`: works / accepted but weak effect / unsupported.
- `quality`: strict / accepted but may be rewritten / unsupported.
- `background: opaque`: works / unsupported.
- `background: transparent`: works / fails / untested.
- `n > 1`: works / fails; if unsupported, loop client-side.
- `partial_images`: useful with streaming / accepted but final image only / unsupported.
- `previous_response_id`: works over HTTP / WebSocket-only / unsupported.
- `input_fidelity`: works / fails / untested.

## Adapter rules

- Keep `images` and `responses` modes explicit internally; do not mix endpoints.
- In `auto`, use Responses mode when `IMAGE_API_MODE=responses` or base ends in `/responses`; otherwise preserve original Images API behavior first.
- Fallback from Images API to Responses API only when the endpoint itself is missing (`404 not found`-style) or a nominal Images response contains no image data.
- Do not fallback on authentication, quota, schema, moderation, timeout, 5xx, or other real failures; switching API families would hide the actual problem.
- If the user explicitly forces `images` while the base points at `/responses`, fail fast instead of constructing invalid paths like `/responses/images/generations`.
- For Responses results, collect `output[].result` from `image_generation_call` items and convert to the same internal save path as Images API.
- Always detect output extension from magic bytes before writing the file.
