# image_api

`image_api` is a lightweight Hermes skill and CLI for image generation and image editing through OpenAI-compatible providers.

It is designed for provider-agnostic use: configure a base URL, API key, and model, then use the same CLI for text-to-image, image editing, multi-reference editing, masks, and structured JSON output. It supports both the classic Images API shape and the newer Responses API image-generation tool shape, with safe auto-detection so users do not need to know which endpoint their provider exposes.

## Highlights

- Text-to-image generation via OpenAI-compatible Images API (`/images/generations`).
- Image editing via Images API (`/images/edits`) with local files, remote URLs, or data URLs.
- Responses API support via `/responses` plus `image_generation` tools.
- `auto` API mode: try the standard Images API first, then fall back to Responses API only when the Images endpoint is missing or returns no image data.
- Multi-reference editing with repeated `--ref` inputs.
- Optional masks with validation and alpha-channel repair helpers.
- Provider-safe parameter handling for size, quality, format, compression, background, moderation, and output count.
- Response parsing for both `b64_json` and URL image payloads.
- Magic-header output format detection, so saved file extensions reflect actual image bytes when providers mislabel formats.
- Clear diagnostics for HTML/proxy responses, JSON errors, unsupported options, endpoint mismatches, and retryable upstream failures.
- JSON output mode for Hermes, cron jobs, scripts, and other automation.

## What this project is

`image_api` is not a web server. It is a small Python CLI packaged as a Hermes skill:

```text
README.md / SKILL.md / references/  -> usage and provider notes
scripts/image_api.py                -> deterministic image API client
tests/                              -> regression tests for API-mode behavior
```

It intentionally keeps runtime dependencies minimal (`requests`; Pillow is optional for mask inspection/fixing).

## Supported API modes

`image_api` has three API modes:

- `auto` — default. Uses configuration and provider behavior to choose the safest mode.
- `images` — classic OpenAI Images API:
  - generation: `POST /images/generations`
  - editing: `POST /images/edits`
- `responses` — OpenAI Responses API shape:
  - `POST /responses`
  - payload includes `tools: [{"type": "image_generation"}]`

### Auto mode behavior

For most users, leave this unset or set it to `auto`:

```bash
IMAGE_API_MODE=auto
```

Auto mode behaves as follows:

1. If `IMAGE_API_MODE=responses`, use Responses API.
2. If `IMAGE_API_BASE` ends with `/responses`, use Responses API and normalize the base URL internally.
3. Otherwise, try the standard Images API first.
4. If the Images endpoint is clearly unavailable, such as `404 Not Found`, or returns no image data, retry once using Responses API.
5. Do not fall back on authentication errors, quota errors, request validation errors, content policy errors, timeouts, or generic upstream failures. Those should remain visible because switching endpoints would hide the real problem.

This lets non-expert users configure a normal `/v1` base URL without knowing the provider's image endpoint details.

## Installation

### Hermes skill install from a local checkout

```bash
mkdir -p ~/.hermes/skills/image_api
cp -R ./* ~/.hermes/skills/image_api/
chmod +x ~/.hermes/skills/image_api/scripts/image_api.py
```

Then start a fresh Hermes session or explicitly load the skill:

```text
/skill image_api
```

### Direct CLI use

You can also run the script directly from this repository:

```bash
python3 scripts/image_api.py --help
```

## Configuration

Hermes convention is to keep secrets in the profile env file, usually:

```text
~/.hermes/.env
```

Check the active path with:

```bash
hermes config env-path
```

Recommended minimal configuration:

```bash
IMAGE_API_BASE=https://api.example.com/v1
IMAGE_API_KEY=sk-your-provider-key
IMAGE_MODEL=gpt-image-2
IMAGE_API_MODE=auto
```

For a provider that exposes images only through a Responses-style endpoint, use the same generic shape:

```bash
IMAGE_API_BASE=https://api.example.com/v1
IMAGE_API_KEY=sk-your-provider-key
IMAGE_MODEL=your-image-capable-model
IMAGE_API_MODE=auto
```

If a provider requires the endpoint path to be explicit, this also works:

```bash
IMAGE_API_BASE=https://api.example.com/v1/responses
IMAGE_API_KEY=sk-your-provider-key
IMAGE_MODEL=your-image-capable-model
IMAGE_API_MODE=auto
```

Do not commit real keys. Examples should use placeholders such as `sk-your-provider-key`.

## Environment variables

- `IMAGE_API_BASE`: Provider base URL. Required. Prefer a generic `/v1` base when available.
- `IMAGE_API_KEY`: Provider API key. Required.
- `IMAGE_MODEL`: Default model. Optional; defaults to `gpt-image-2` when unset.
- `IMAGE_API_MODE`: `auto`, `images`, or `responses`. Optional; defaults to `auto`.
- `IMAGE_OUT_DIR`: Output directory. Optional; defaults to `/tmp/gptimage`.

## Quick start

Load env variables, then call the script:

```bash
set -a
source ~/.hermes/.env
set +a

python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  "A clean vector-style blue checkmark icon on a white background" \
  --size 1024x1024 \
  --format png
```

The output is JSON when `--json` is used:

```json
{
  "ok": true,
  "paths": ["/tmp/gptimage/0520_120000_A_clean_vector_style_blue_check_0.png"],
  "used_params": {
    "mode": "generate",
    "model": "gpt-image-2",
    "size": "1024x1024",
    "quality": "low",
    "output_format": "png",
    "n": 1,
    "moderation": "low",
    "api_mode": "images"
  },
  "endpoint": "https://api.example.com/v1"
}
```

`api_mode` may be `responses` when auto fallback selects the Responses API.

## Common commands

### Text-to-image

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  "A minimalist product photo of a matte black water bottle" \
  --size 1024x1024 \
  --quality high \
  --format png
```

### Image editing

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image source.png \
  "Change the background to a soft studio gradient"
```

### URL or data URL image input

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image https://example.com/source.png \
  "Make the object blue while preserving shape"
```

### Multi-reference editing

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image main.png \
  --ref palette.png \
  --ref style-reference.png \
  "Apply the color palette and style reference to the main image"
```

### Masked editing

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image source.png \
  --mask mask.png \
  --validate-mask \
  "Replace only the masked region with a red umbrella"
```

If the mask lacks alpha information and Pillow is installed, you can repair it before upload:

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image source.png \
  --mask gray-mask.png \
  --fix-mask-alpha \
  "Edit the masked area only"
```

### Force a specific API mode

Most users should not need this. Use it when debugging provider behavior:

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --api-mode images \
  "A small isometric house icon"

python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --api-mode responses \
  "A small isometric house icon"
```

## CLI parameters

- `prompt`: Required text prompt or edit instruction.
- `--edit`: Use edit mode.
- `--image`: Primary image path, URL, or data URL. Required for edit mode.
- `--ref`: Additional reference image. Repeatable.
- `--mask`: Mask image path, URL, or data URL.
- `--model`: Override `IMAGE_MODEL` for one call.
- `--size`: Image size, default `1024x1024`. Also accepts provider-supported values such as `auto` where available.
- `--quality`: `low`, `medium`, `high`, or `auto`.
- `--n`: Number of images. Images API may support multiple outputs; Responses mode currently requires `1`.
- `--format`: `png`, `jpeg`, or `webp`.
- `--compression`: `0`-`100`, typically for `jpeg`/`webp` providers.
- `--background`: `opaque`, `auto`, or `transparent`. Some Responses providers reject `transparent`; the client blocks known-unsafe combinations.
- `--moderation`: `auto` or `low`.
- `--outdir`, `-o`: Output directory.
- `--prefix`: Optional filename prefix.
- `--timeout`: Request timeout in seconds.
- `--validate-mask`: Check mask size and alpha before editing.
- `--fix-mask-alpha`: Convert grayscale mask to RGBA alpha mask when possible.
- `--api-mode`: `auto`, `images`, or `responses`.
- `--json`: Emit structured JSON for automation.

## Output and file handling

Generated files are written to `IMAGE_OUT_DIR`, `--outdir`, or `/tmp/gptimage`.

The client saves images using the actual byte format, not only the provider-declared `output_format`. This matters because some providers may claim `webp` or `jpeg` while returning PNG bytes.

Supported output byte signatures:

- PNG: `89 50 4E 47`
- JPEG: `FF D8 FF`
- WebP: `RIFF .... WEBP`

## Provider compatibility guidance

Use generic configuration in public docs and examples. Provider-specific quirks should live in `references/` rather than being repeated throughout the README.

A provider may differ in these areas:

- whether image generation is exposed through Images API, Responses API, or both;
- whether edit mode accepts multipart `image[]`, Responses `input_image`, or masks;
- whether `n > 1` is supported;
- whether `transparent` backgrounds are supported;
- whether `quality`, `output_format`, and `compression` are honored exactly;
- whether returned image bytes match the requested format.

When adding a new provider, prefer:

1. Configure `IMAGE_API_BASE` as a normal `/v1` URL.
2. Leave `IMAGE_API_MODE=auto`.
3. Run one text-to-image smoke test.
4. Run one edit test if the provider claims edit support.
5. Add a short provider note under `references/` only if behavior is non-standard.

## Error handling and retry policy

The client retries transient failures such as rate limits and gateway/server errors. It does not hide permanent errors.

Auto fallback from Images API to Responses API is intentionally narrow:

- Fallback is allowed for missing image endpoints or empty image payloads.
- Fallback is not allowed for bad credentials, quota failures, invalid request parameters, content policy responses, timeouts, or general upstream errors.

This makes configuration easier without masking real failures.

## Resolution constraints

The client validates common provider constraints before sending requests:

- longest side: `<= 3840`
- total pixels: approximately `655,360` to `8,294,400`
- width and height must be divisible by `16`
- aspect ratio should be `<= 3:1`
- very large portrait sizes may be provider-dependent even when they pass local validation

See `references/resolution-guide.md` for more detail.

## Testing

Run the regression tests:

```bash
python3 -m pytest tests/test_responses_mode.py -q
python3 -m py_compile scripts/image_api.py
```

Optional live smoke test, assuming `~/.hermes/.env` contains valid provider credentials:

```bash
set -a
source ~/.hermes/.env
set +a

python3 scripts/image_api.py \
  --json \
  "A tiny black plus icon on a white background" \
  --size 1024x1024 \
  --format png \
  --outdir /tmp/gptimage_smoke
```

## Project structure

```text
image_api/
├── README.md
├── SKILL.md
├── CHANGELOG.md
├── LICENSE
├── .env.example
├── scripts/
│   └── image_api.py
├── tests/
│   └── test_responses_mode.py
└── references/
    ├── fields.md
    ├── provider-quirks.md
    ├── resolution-guide.md
    ├── cpa-provider-quirks.md
    ├── gateway-image-debug.md
    ├── image-delivery-debugging.md
    └── provider-specific compatibility notes
```

## Security notes

- Keep API keys in `~/.hermes/.env` or another local secret store.
- Do not commit `.env` files or real provider keys.
- Use placeholders in docs and issues.
- Treat generated images as user data; avoid uploading them elsewhere unless the user explicitly requests it.

## License

MIT

## Friend Link

[LinuxDo](https://www.linux.do)
