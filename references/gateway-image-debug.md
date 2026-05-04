# Telegram Gateway 图片丢失排查

## 症状
用户在 Telegram 发了图片，但模型对话上下文中看不到图片附件。用户可能说"用这张图"、"你看不到吗"等。

## 排查步骤

### 1. 确认图片是否下载到本地
```bash
ls -lt ~/.hermes/image_cache/ | head -5
```
看时间戳是否与用户发消息的时间匹配。最新的 .jpg 文件就是用户刚发的。

### 2. 确认网关是否处理了图片
```bash
grep "Cached user photo\|Flushing photo\|Image routing" ~/.hermes/logs/gateway.log | tail -10
```
正常流程应该是：
```
[Telegram] Cached user photo at ~/.hermes/image_cache/img_xxx.jpg
[Telegram] Flushing photo batch ... with 1 image(s)
Image routing: native (model supports vision). 1 image(s) will be attached inline.
```

### 3. 检查是否有错误
```bash
grep -i "error\|failed\|skipping" ~/.hermes/logs/gateway.log | tail -10
```

## 常见原因
- **Provider 不支持 vision** — 网关误判模型支持 inline 图片，但 API 端静默丢弃
- **photo-burst 合并问题** — 网关有 photo burst 机制，多张快速发送的图可能被合并或丢失
- **多轮对话中图片丢失** — 第一张图成功，后续图被 provider 丢弃（provider 端行为不稳定）

## 解决方案
找到本地图片路径后，直接用 image-api 的 `--edit --image "<path>"` 模式传入参考图，绕过模型上下文的限制。

## 关键路径
- 图片缓存：`~/.hermes/image_cache/`
- 网关日志：`~/.hermes/logs/gateway.log`
- 生成输出：`/tmp/gptimage/`
