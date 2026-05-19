# Responses API provider adapter

This reference documents the generic adapter contract for providers that expose image generation through an OpenAI-compatible Responses API.

It intentionally avoids naming private providers, personal routing models, account-specific endpoints, or real credentials. Keep concrete provider discoveries in private notes unless they are already public, non-sensitive, and useful to external users.

## Generic provider contract

A Responses-style image provider usually accepts:

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

Endpoint:

```text
POST /responses
```

Expected image result location:

```text
output[*].result on output entries with type == "image_generation_call"
```

The result is base64 image data. Save by decoding and detecting the real magic header, not by trusting `output_format`.

## Edit / multi-reference payload shape

```json
{
  "model": "your-image-capable-model",
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

Preferred generic shape:

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

If a provider requires a different mask schema, record it as a sanitized compatibility note and add a regression test where possible.

## Compatibility categories

Stable enough to support:

- Text-to-image.
- Single-image edit.
- Multi-reference edit with multiple `input_image` entries.
- Mask edit with `input_image_mask.image_url`.
- Common sizes such as `1024x1024`, `1024x1536`, `1536x1024`.
- PNG and JPEG output.

Use cautiously:

- `quality`: some providers accept it but may rewrite/downgrade.
- `output_format: webp`: some providers accept the request but return PNG bytes.
- `output_compression`: may be accepted but have weak or provider-dependent effects.
- `partial_images`: useful mainly with streaming providers; non-streaming calls may return only the final image.

Avoid by default unless tested:

- `n > 1`: many Responses image providers only support one image per request; loop client-side.
- `background: transparent`: frequently provider-specific.
- `previous_response_id`: may require WebSocket or stateful APIs.
- `input_fidelity: high`: provider-specific and not universally supported.

## Auto-detection / anti-mixing strategy

Use `auto` as the default so users do not need to know the provider's API family:

1. If `IMAGE_API_BASE` ends in `/responses`, normalize base to `/v1` and use Responses mode directly.
2. If `IMAGE_API_MODE=responses`, use Responses mode directly.
3. Otherwise, try original Images API first to preserve providers that support `/images/generations` and `/images/edits`.
4. Only fallback from Images to Responses when the endpoint itself is missing (`404 not found`-style) or a nominal Images response contains no image data.
5. Do not fallback on authentication, quota, schema, moderation, timeout, 5xx, or other real failures; switching API families would hide the actual problem.
6. If the user explicitly forces `images` while the base points at `/responses`, fail fast instead of constructing invalid paths like `/responses/images/generations`.

## Test pattern

Add unit tests that monkeypatch network calls and assert:

- `images` mode still sends `/images/generations` / `/images/edits`.
- `responses` mode sends `/responses` with `tools: [{"type":"image_generation"}]`.
- `auto` mode falls back from `/images/generations` to `/responses` only on missing endpoint/empty-image cases.
- `auto` mode does not fallback on `401` or other real errors.
