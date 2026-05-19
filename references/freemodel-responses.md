# freemodel Responses API provider notes

Use this reference when adapting or testing `image_api` against freemodel or another provider that exposes image generation through OpenAI Responses API rather than the legacy Images API endpoints.

## Provider shape

freemodel supports image generation through:

```text
POST https://api.freemodel.dev/v1/responses
model: gpt-5.5
 tools: [{"type": "image_generation"}]
```

It did not support these Images API endpoints in testing:

```text
/v1/images/generations
/v1/images/edits
```

So the correct `image_api` configuration is either:

```bash
IMAGE_API_BASE=https://api.freemodel.dev/v1/responses
IMAGE_MODEL=gpt-5.5
IMAGE_API_MODE=auto
```

or simply:

```bash
IMAGE_API_BASE=https://api.freemodel.dev/v1
IMAGE_MODEL=gpt-5.5
IMAGE_API_MODE=auto
```

With `auto`, `image_api` first tries Images API for a normal `/v1` base, then falls back to `/responses` only when the Images endpoint is missing or returns no image data. It does not fallback on auth, quota, moderation, schema, timeout, or upstream errors.

When `IMAGE_API_BASE` ends in `/responses`, `image_api` should normalize the base to `/v1` and use `/responses` exactly once. Do not append Images API paths to a `/responses` base.

## Confirmed working payloads

### Text-to-image

```json
{
  "model": "gpt-5.5",
  "input": "Generate a simple icon on a white background.",
  "tools": [{"type": "image_generation", "size": "1024x1024", "output_format": "png"}]
}
```

The returned image is in `output[].result` for entries with `type: "image_generation_call"`.

### Single-image edit

```json
{
  "model": "gpt-5.5",
  "input": [{
    "role": "user",
    "content": [
      {"type": "input_text", "text": "Change the icon color to blue."},
      {"type": "input_image", "image_url": "data:image/png;base64,..."}
    ]
  }],
  "tools": [{"type": "image_generation"}]
}
```

### Multi-reference edit

Pass multiple `input_image` content items after the text prompt. freemodel/gpt-5.5 returned `action: edit` and a valid image.

### Mask edit

The working mask shape is:

```json
{
  "tools": [{
    "type": "image_generation",
    "input_image_mask": {"image_url": "data:image/png;base64,..."}
  }]
}
```

Do not pass `input_image_mask` as a bare string, and do not include `type: "input_image"` inside the mask object; both failed in testing.

## Parameter behavior observed with gpt-5.5

- `size`: works for `1024x1024`, `1024x1536`, `1536x1024`.
- `output_format: png`: works and returns PNG.
- `output_format: jpeg`: works and returns JPEG.
- `output_format: webp`: request succeeds but actual bytes may still be PNG. Save by magic header, not by reported field.
- `output_compression`: request succeeds for JPEG but effect may be small; WebP remains unreliable.
- `quality`: accepted but provider may rewrite or downgrade (`low`/`medium`/`high` are not strict promises).
- `background: opaque`: works.
- `background: transparent`: failed with upstream 502; block or avoid by default.
- `n > 1`: failed with upstream/Cloudflare 502; generate multiple images by looping one request at a time.
- `partial_images` without streaming: accepted but only final image is useful.
- `previous_response_id`: HTTP `/responses` returned `previous_response_id is only supported on Responses WebSocket v2`; for multi-turn edits, pass the prior output image back as `input_image`.

## Vision observations

`gpt-5.5` accepted `input_image` for text output with `detail: low`, `high`, `original`, and `auto`. `auto` behaved close to `original` in token usage, consistent with OpenAI docs. Use `detail: low` for cheap descriptions and `high/original` for detail-sensitive analysis.

## Adapter rules

- Keep `images` and `responses` modes explicit internally; do not mix endpoints.
- In `auto`, use Responses mode only when `IMAGE_API_MODE=responses` or base ends in `/responses`; otherwise preserve original Images API behavior.
- If base ends in `/responses` but mode is forced to `images`, fail early with a clear configuration error.
- For Responses results, collect `output[].result` from `image_generation_call` items and convert to the same internal `data[].b64_json` save path as Images API.
- Always detect output extension from magic bytes before writing the file.
