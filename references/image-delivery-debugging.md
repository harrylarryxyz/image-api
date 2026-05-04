# Image Delivery Debugging

When a user says "I sent an image but you didn't receive it" in a gateway context (Telegram, Discord, etc.).

## Quick Diagnosis

```bash
# 1. Check image cache — did the platform download it?
ls -lt ~/.hermes/image_cache/ | head -5

# 2. Check gateway logs — did it route the image?
grep -i "cached.*photo\|flushing\|Image routing" ~/.hermes/logs/gateway.log | tail -10

# 3. Check model switch — was the model changed mid-session?
grep -i "Model switched\|model.*change" ~/.hermes/logs/agent.log | tail -5
```

## Common Failure Modes

### Image cached but not in model context
- Gateway log shows `Image routing: native (model supports vision)`
- Image is in `~/.hermes/image_cache/`
- But model didn't "see" it

**Cause**: Provider silently drops inline images. The gateway's `models_dev` metadata says the model supports vision (`attachment=True`), but the actual API doesn't handle base64 `image_url` content parts correctly.

**Confirmed case**: xiaomi mimo-v2.5-pro drops base64 images silently; mimo-v2.5 handles them fine.

**Fix**:
```bash
# Option A: Force text mode (vision_analyze pre-processes images)
hermes config set agent.image_input_mode text

# Option B: Configure a dedicated vision model for pre-processing
hermes config set auxiliary.vision.provider google
hermes config set auxiliary.vision.model gemini-2.5-flash
```

### Image not cached at all
- Nothing in `~/.hermes/image_cache/`
- No "Cached user photo" in gateway log

**Cause**: Platform adapter failed to download. Check gateway logs for errors.

### vision_analyze fails
- Gateway log shows `Image routing: text (mode=...)`
- But model still doesn't understand the image

**Cause**: The auxiliary vision model failed. Check agent.log for errors.

## Decision Flow

```
User says image not received
  → ls ~/.hermes/image_cache/ (newest file?)
    → NO: platform download issue
    → YES: check gateway.log for routing
      → "native" + model didn't see it: provider drops inline images → fix with text mode
      → "text" + model didn't understand: vision_analyze failed → check auxiliary config
      → No routing log at all: image wasn't processed as image (might be wrong content type)
```
