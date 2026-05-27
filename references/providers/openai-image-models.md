# OpenAI Image Model Notes

This note documents model-specific behavior that generic OpenAI-compatible providers often mirror. Keep normal examples provider-neutral; use this page when debugging OpenAI image model compatibility.

## GPT Image 2

Recommended generic configuration:

```bash
IMAGE_API_BASE=https://api.example.com/v1
IMAGE_API_KEY=YOUR_PROVIDER_API_KEY
IMAGE_MODEL=gpt-image-2
IMAGE_API_MODE=auto
```

Supported expectations:

- text-to-image generation;
- reference-image editing;
- multi-reference editing where the upstream supports multiple multipart images;
- PNG, JPEG, and WebP byte outputs, with saved extensions detected from actual magic headers.

Important constraints:

- Transparent background is not supported by `gpt-image-2`. Use `gpt-image-1.5` for transparent PNG/WebP output, or remove `--background transparent`. The client fails fast instead of silently rewriting the model.
- High-resolution or complex edit jobs may need a longer timeout, commonly `--timeout 600` for slow gateways or Azure-style deployments.
- In Responses mode, multiple outputs may be limited; use separate calls when `--n` is rejected.
- If a user explicitly asks for this model, the client should fail clearly on model-specific validation errors and should not switch to another provider or model silently.

Suggested smoke matrix:

1. generate with no reference image;
2. edit with one primary image;
3. edit with one primary image plus one reference;
4. edit with multiple references;
5. edit with a mask;
6. URL or data-URL image input;
7. rejected transparent background request with a clear diagnostic.
