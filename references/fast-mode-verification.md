# Fast-mode verification for image_api

Session-derived checklist for confirming the quick/low-cost generation path. Keep this provider-agnostic and do not record private API keys.

## What “fast mode” means

`image_api` does not currently expose a dedicated `--fast` flag. In normal Hermes usage, “fast mode” means the quick baseline parameters:

```bash
--quality low --size 1024x1024 --format png --moderation low
```

## Verification checklist

1. Source runtime env and export all image-related variables, not just key/base:

```bash
source ~/.hermes/.env && export IMAGE_API_KEY IMAGE_API_BASE IMAGE_MODEL IMAGE_API_MODE
```

2. Confirm the configured model is image-capable. Do not reuse the chat/text model name as `IMAGE_MODEL` unless the provider explicitly exposes it as an image model.

3. Run a minimal prompt with `--json` and the fast baseline:

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  "simple blue circle icon on white background" \
  --size 1024x1024 \
  --quality low \
  --format png \
  --moderation low \
  --prefix fast_check
```

4. Treat success as all of the following:

- JSON contains `"ok": true`.
- `used_params.quality` is `low`.
- The configured `IMAGE_MODEL` or one-off `--model` value is image-capable; the JSON output intentionally does **not** echo the model route.
- Output path exists.
- Output bytes match a real image magic header, e.g. PNG `89 50 4E 47 0D 0A 1A 0A`.

## Common failure

Error pattern:

```text
images endpoint requires an image model, got "<text-model>"
```

Fix: set `IMAGE_MODEL` to a provider-supported image model and retry the same fast baseline. This is a configuration/model-class issue, not a failure of the fast baseline itself.
