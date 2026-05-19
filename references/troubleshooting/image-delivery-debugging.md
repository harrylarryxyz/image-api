# Image delivery debugging

Use this reference when a user says they sent an image but the agent did not receive or use it correctly in an interactive gateway context.

This document is sanitized and gateway-agnostic. Do not record private chat IDs, personal model routes, provider account names, or real credentials here.

## Quick diagnosis

```bash
# 1. Check image cache — did the platform download it?
ls -lt ~/.hermes/image_cache/ | head -5

# 2. Check gateway logs — did it route the image?
grep -i "cached.*photo\|cached.*image\|flushing\|Image routing" ~/.hermes/logs/gateway.log | tail -10

# 3. Check model or route changes around the same time
grep -i "Model switched\|model.*change" ~/.hermes/logs/agent.log | tail -5
```

For named profiles or custom deployments, replace `~/.hermes/` with the active Hermes home path.

## Common failure modes

### Image cached but not in model context

Signals:

- Gateway logs show image routing.
- A recent image exists in `~/.hermes/image_cache/`.
- The model still behaves as if no image was attached.

Possible causes:

- The active model route does not actually support inline image input.
- Provider metadata claims vision support, but the upstream API drops base64 `image_url` parts.
- A gateway adapter cached the image but did not attach it to the current turn.

Fix options:

```bash
# Option A: force text mode so vision_analyze pre-processes images
hermes config set agent.image_input_mode text

# Option B: configure a dedicated auxiliary vision provider/model
hermes config set auxiliary.vision.provider <provider>
hermes config set auxiliary.vision.model <vision-model>
```

Restart the gateway or start a fresh session if configuration is cached.

### Image not cached at all

Signals:

- Nothing recent appears in `~/.hermes/image_cache/`.
- Gateway logs do not show image caching.

Likely cause: the platform adapter failed to download the image or did not treat the incoming attachment as an image. Check gateway logs for platform-specific errors.

### Vision preprocessing fails

Signals:

- Gateway logs show text/vision preprocessing mode.
- The final model still misunderstands the image.

Likely cause: the auxiliary vision route failed or returned a poor description. Check agent logs and run a direct `vision_analyze` probe if needed.

## Decision flow

```text
User says image was not received
  → Check ~/.hermes/image_cache/ for a recent file
    → No file: platform download/cache issue
    → File exists: check gateway.log for routing
      → Routed native but model did not see it: inline image route likely unsupported
      → Routed text but model misunderstood it: auxiliary vision route may be bad
      → No routing log: gateway did not process the attachment as an image
```

## Workaround for image_api workflows

If the user's goal is image editing/reference generation and the cached image file exists, pass that file path directly to `image_api`:

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image "<cached-image-path>" \
  "<user edit instruction>"
```

Do not convert the image to a text description unless the user explicitly asks for description/analysis. For image generation workflows, the image itself is usually the intended reference input.
