# Distinguishing image_api fast from Hermes Priority Processing

This note captures a user correction from a session where "fast" was misinterpreted.

## Two unrelated meanings of "fast"

1. **Hermes `/fast` / Priority Processing**
   - User-facing status often appears as:
     - `⚡ ✓ Priority Processing: FAST (saved to config)`
     - `_(takes effect on next message)_`
   - This is Hermes Agent runtime configuration, not image generation quality.
   - Config key: `agent.service_tier: fast`
   - For supported OpenAI-style models, Hermes resolves this to request overrides like:
     - `{"service_tier": "priority"}`
   - It belongs to the `hermes-agent` class of tasks. Do not use `image_api` probes to validate it.

2. **`image_api` fast / quick baseline**
   - `image_api` has no standalone `--fast` flag.
   - In this skill, "fast" only means the quick baseline parameters:
     - `--quality low --size 1024x1024 --format png --moderation low`
   - Validate by checking `--json` output, image model, file existence, and image magic header.

## Disambiguation rule

Before testing or changing anything, look at the user's exact quoted/status text:

- If they quote `Priority Processing`, `/fast`, `saved to config`, or `takes effect on next message`, treat it as **Hermes `/fast` Priority Processing**.
- If they ask about generated image speed/quality, `--quality`, or output image parameters, treat it as **`image_api` quick baseline**.

If the user is replying to a Hermes status line, do not reinterpret it as image_api fast mode, even if the session also involved image generation.

## Minimal Hermes validation pattern

When a user asks whether Hermes FAST is enabled:

- Check config/readiness via Hermes mechanisms, not image_api:
  - `agent.service_tier` should be `fast` or resolve to priority mode.
  - Current model should support Hermes fast mode.
  - Expected override is usually `{"service_tier": "priority"}` for OpenAI-style models, or `{"speed": "fast"}` for Anthropic fast-mode models.
- If probing an API response, report both:
  - what Hermes sent/should send, and
  - what the upstream/provider echoed back (some proxies may echo `service_tier: auto` even when the request included priority).

## Response guidance after this correction

If you made the confusion:

- Apologize briefly and explicitly name the two meanings.
- State that `image_api --quality low` was the wrong interpretation.
- Give the verified Hermes status/override if checked.
- Avoid long defensive explanations.
