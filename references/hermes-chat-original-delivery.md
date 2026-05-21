# Hermes chat gateways: preview + original image delivery

Use this reference when delivering generated images through Hermes chat gateways (especially Telegram) and the user wants both an in-chat preview and the original file bytes.

## Pattern

1. Send the image preview normally:

```text
MEDIA:/absolute/path/to/image.png
```

2. Send the same image path again as a document/file attachment:

```text
[[as_document]]
MEDIA:/absolute/path/to/image.png
```

Do **not** zip the image just to preserve original bytes. The `[[as_document]]` marker tells the gateway to use document/file delivery (Telegram `sendDocument`) instead of photo delivery, which avoids Telegram photo recompression while keeping the filename and original file attachment semantics.

## When to use

- User asks for “原始图片文件”, “附件”, “原图”, “without compression”, or “as file”.
- You want a convenient chat preview plus a high-quality downloadable original.

## Pitfalls

- A zip archive is not equivalent to “original image file attachment” unless the user explicitly asks for an archive.
- Keep public docs provider-agnostic: mention gateway delivery behavior, not private image providers, keys, hostnames, or model routes.
