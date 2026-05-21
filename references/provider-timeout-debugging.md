# Provider timeout and HTML error debugging

Use this reference when `image_api` fails with a non-JSON response such as `HTTP 504` and `Content-Type: text/html`.

## What to verify

1. Do not assume the failure is local. A short HTML body usually indicates a gateway/load-balancer/proxy error before the provider returns JSON.
2. If the user asks what the returned text/HTML was, make one sanitized direct probe to the same endpoint and capture:
   - HTTP status
   - content type
   - content length
   - first 1,000-5,000 characters of response body
3. Redact API keys and bearer tokens before showing any body preview.
4. Compare at least two prompts when diagnosing likely cause:
   - the user's failing prompt or a safe/sanitized equivalent
   - a very simple control prompt such as `Simple blue checkmark icon on white background.`
5. Keep size, model, API mode, and format the same across probes unless specifically testing those variables.

## Interpreting results

- Complex scene fails with `504` but simple icon succeeds: provider is reachable, but the image backend likely times out on complex/person/scene prompts or on a slower routing path.
- Both complex and simple prompts fail with the same HTML timeout: provider/gateway is likely generally unhealthy at that moment.
- JSON moderation or validation error: treat as provider/model response, not gateway timeout.
- HTML body like `<h1>504 Gateway Time-out</h1>` with a short server marker such as `alb`: likely load balancer timeout.

## Reporting pattern

Keep the report concise:

```text
image_api failed with HTTP 504 text/html. Direct probe body was:
<html>...</html>

Simple control prompt: succeeded/failed.
Likely cause: provider gateway timeout vs prompt-specific backend timeout.
```

Do not leak real provider hosts, keys, private model routes, or account identifiers in public docs or skill references.
