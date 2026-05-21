# Conversational gateway image routing debug

Use this reference when a user sends an image through an interactive gateway, but the agent cannot see it in the model context.

This document is gateway-agnostic. Commands use Hermes default paths as examples; adapt paths for named profiles or custom deployments.

## Symptoms

The user sends an image and says something like:

- "use this image"
- "make this into..."
- "you can't see it?"

But the current model turn contains no attached image object.

## Debug steps

### 1. Check whether the gateway cached the image locally

```bash
ls -lt ~/.hermes/image_cache/ | head -5
```

Compare timestamps with the user's message time. The newest image file is often the file the user just sent.

### 2. Check gateway logs for image handling

```bash
grep "Cached user photo\|Flushing photo\|Image routing" ~/.hermes/logs/gateway.log | tail -10
```

A healthy flow may look like:

```text
[Gateway] Cached user image at ~/.hermes/image_cache/img_xxx.jpg
[Gateway] Flushing image batch ... with 1 image(s)
Image routing: native or text; 1 image(s) will be attached or summarized.
```

### 3. Check errors

```bash
grep -i "error\|failed\|skipping" ~/.hermes/logs/gateway.log | tail -10
```

## Common causes

- The active model route does not support inline image input.
- The gateway cached the file but did not attach it to the current turn.
- Multiple images were sent quickly and were batched unexpectedly.
- The upstream provider accepted the request but ignored image input.
- A profile-specific cache/log path differs from the default path.

## Workaround

If the file exists locally, pass the path directly to `image_api` edit mode:

```bash
python3 ~/.hermes/skills/image_api/scripts/image_api.py \
  --json \
  --edit \
  --image "<cached-image-path>" \
  "<user edit instruction>"
```

Do not call vision analysis just to describe the image unless the user asked for a description. In image-generation workflows, a sent image is usually intended as an edit/reference input.

## Key paths

- Image cache: `~/.hermes/image_cache/`
- Gateway logs: `~/.hermes/logs/gateway.log`
- Default generation output: `/tmp/image_api/`
