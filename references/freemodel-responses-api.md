# freemodel Responses API compatibility notes

Session-derived provider notes for adapting `image_api` to providers that expose image generation through OpenAI-compatible `/responses` rather than `/images/*`.

## Known-good freemodel shape

- Base URL may be either:
  - `https://api.freemodel.dev/v1`
  - `https://api.freemodel.dev/v1/responses`
- Model tested successfully: `gpt-5.5`
- Endpoint: `POST /responses`
- Tool: `{"type": "image_generation"}`
- Image result field: `output[*].result` on `image_generation_call` objects
- Result is base64 image data; save by decoding and detecting real magic header, not by trusting `output_format`.

## Generate payload shape

```json
{
  "model": "gpt-5.5",
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

## Edit / multi-reference payload shape

```json
{
  "model": "gpt-5.5",
  "input": [
    {
      "role": "user",
      "content": [
        {"type": "input_text", "text": "Change the object color, keep background."},
        {"type": "input_image", "image_url": "data:image/png;base64,..."},
        {"type": "input_image", "image_url": "data:image/png;base64,..."}
      ]
    }
  ],
  "tools": [
    {"type": "image_generation"}
  ]
}
```

## Mask payload shape

freemodel accepted this shape:

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

Avoid these mask shapes for freemodel: a bare data URL string, or an object with `type: input_image`; both produced upstream failures during testing.

## Compatibility results

Stable enough to support:

- Text-to-image
- Single-image edit
- Multi-reference edit with multiple `input_image` entries
- Mask edit with `input_image_mask.image_url`
- `size` such as `1024x1024`, `1024x1536`, `1536x1024`
- PNG and JPEG output
- Vision detail options in plain Responses calls (`low`, `high`, `original`, `auto`)

Use cautiously:

- `quality`: accepted but may be rewritten by provider.
- `output_format: webp`: may return a PNG despite claiming WebP.
- `output_compression`: accepted for JPEG but effect may be modest.
- `partial_images`: non-streaming requests return only final image.

Avoid by default:

- `n > 1`: produced 502; loop client-side instead.
- `background: transparent`: produced 502; prefer `opaque` or omit.
- `previous_response_id`: HTTP endpoint returned that it is only supported on Responses WebSocket v2.
- `input_fidelity: high`: produced upstream errors.

## Auto-detection / anti-mixing strategy

The user explicitly wanted users not to need to know the provider's API family. Use `auto` as the default:

1. If `IMAGE_API_BASE` ends in `/responses`, normalize base to `/v1` and use Responses mode directly.
2. If `IMAGE_API_MODE=responses`, use Responses mode directly.
3. Otherwise, try original Images API first to preserve providers that support `/images/generations` and `/images/edits`.
4. Only fallback from Images to Responses when the endpoint itself is missing (`404 not found`-style) or a nominal Images response contains no image data.
5. Do **not** fallback on authentication, quota, schema, moderation, timeout, 5xx, or other real failures; switching API families would hide the actual problem.
6. If the user explicitly forces `images` while the base points at `/responses`, fail fast instead of constructing invalid paths like `/responses/images/generations`.

## Test pattern

Add unit tests that monkeypatch network calls and assert:

- `images` mode still sends `/images/generations` / `/images/edits`.
- `responses` mode sends `/responses` with `tools: [{"type":"image_generation"}]`.
- `auto` mode falls back from `/images/generations` to `/responses` only on missing endpoint/empty-image cases.
- `auto` mode does not fallback on `401` or other real errors.
