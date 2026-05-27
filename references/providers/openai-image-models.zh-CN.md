# OpenAI 图像模型说明

本页记录常见 OpenAI 图像模型行为，很多 OpenAI-compatible provider 会参考这些行为。常规 README 继续保持 provider-neutral；排查 OpenAI 图像兼容性时看这里。

## GPT Image 2

推荐的通用配置：

```bash
IMAGE_API_BASE=https://api.example.com/v1
IMAGE_API_KEY=YOUR_PROVIDER_API_KEY
IMAGE_MODEL=gpt-image-2
IMAGE_API_MODE=auto
```

预期支持：

- 文生图；
- 参考图编辑；
- 上游支持时的多参考图编辑；
- PNG、JPEG、WebP 输出，保存时按真实 magic header 判断扩展名。

重要限制：

- `gpt-image-2` 不支持透明背景。透明 PNG/WebP 请用 `gpt-image-1.5`，或移除 `--background transparent`。客户端会提前失败，不会静默改写模型。
- 高分辨率或复杂编辑可能需要更长超时；慢网关或 Azure 类部署建议 `--timeout 600`。
- Responses 模式下多张输出可能受限；如果 `--n` 被拒绝，应拆成多次请求。
- 如果用户显式指定这个模型，客户端应清楚失败，不应静默切到其它 provider 或模型。

建议 smoke matrix：

1. 无参考图生成；
2. 单主图编辑；
3. 主图 + 1 张参考图编辑；
4. 多参考图编辑；
5. 带 mask 编辑；
6. URL 或 data URL 图片输入；
7. 透明背景请求被拒绝且错误清楚。
