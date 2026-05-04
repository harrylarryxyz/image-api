#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image API - 通用封装 v4.1.0
基于 OpenAI Image API (Generations + Edits)

API: /v1/images/generations  生成
API: /v1/images/edits        编辑

v4.0.0 重构: curl 子进程 → requests 原生，提升 edit 模式稳定性
v4.1.0 合并: 多参考图(--ref)、参数预校验、mask 校验修复、延迟配置加载

环境变量:
  IMAGE_API_BASE  - API 端点 (如 https://api.example.com/v1)
  IMAGE_API_KEY   - API 密钥
  IMAGE_OUT_DIR   - 输出目录 (默认 /tmp/gptimage)

使用示例:
  普通模式:
    python3 image_api.py "A beautiful sunset" --size 1536x1024 --quality high
    python3 image_api.py "Make it green" --edit --image source.png

  多参考图编辑:
    python3 image_api.py "Combine these" --edit --image main.png --ref ref1.png --ref ref2.png

  JSON 输出模式（用于程序化调用）:
    python3 image_api.py "A cat" --size 1024x1024 --json
    python3 image_api.py "Make it blue" --edit --image https://example.com/img.png --json
"""

import json
import base64
import os
import sys
import time
import uuid
import re
import mimetypes
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

try:
    import requests as _requests
except ImportError:
    print("错误: requests 库未安装。请运行: pip install requests", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# 配置 - 延迟加载（避免 --help / 纯参数校验时因缺 env 直接退出）
# =============================================================================

DEFAULT_OUTDIR = os.environ.get("IMAGE_OUT_DIR", "/tmp/gptimage")
DEFAULT_TIMEOUT = 900
DEFAULT_MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")
MAX_RETRIES = 2
RETRY_DELAY = 5  # seconds

# 参数校验常量
VALID_QUALITIES = {"low", "medium", "high", "auto"}
VALID_BACKGROUNDS = {"opaque", "auto", "transparent"}
VALID_FORMATS = {"png", "jpeg", "webp"}
MIN_PIXELS = 655_360
MAX_PIXELS = 8_294_400
MAX_EDGE = 3840
MAX_ASPECT_RATIO = 3.0

# 全局配置（延迟初始化）
API_BASE: Optional[str] = None
API_KEY: Optional[str] = None


def ensure_runtime_config() -> Tuple[str, str]:
    """延迟读取环境变量，首次实际调用时才初始化。"""
    global API_BASE, API_KEY
    if API_BASE and API_KEY:
        return API_BASE, API_KEY

    missing = []
    base_url = os.environ.get("IMAGE_API_BASE", "").rstrip("/")
    api_key = os.environ.get("IMAGE_API_KEY", "")
    if not base_url:
        missing.append("IMAGE_API_BASE")
    if not api_key:
        missing.append("IMAGE_API_KEY")
    if missing:
        raise RuntimeError(
            "Image API 尚未配置：缺少 " + ", ".join(missing) + "。"
            "请在 skill 目录创建 .env：复制 .env.example 为 .env，"
            "然后填写 IMAGE_API_BASE 和 IMAGE_API_KEY。"
            "例如 IMAGE_API_BASE=http://api.example.com/v1。"
        )

    API_BASE = base_url
    API_KEY = api_key
    _session.headers.update({
        "Authorization": f"Bearer {API_KEY}",
    })
    return API_BASE, API_KEY


# requests Session（复用连接）
_session = _requests.Session()
_session.headers.update({
    "User-Agent": "Image-API/4.1",
})


# =============================================================================
# 参数预校验
# =============================================================================

def _is_gpt_image_2(model: str) -> bool:
    return model.strip().lower() == "gpt-image-2"


def _validate_image_options(
    *,
    model: str,
    size: Optional[str] = None,
    quality: Optional[str] = None,
    fmt: Optional[str] = None,
    output_compression: Optional[int] = None,
    background: Optional[str] = None,
) -> None:
    """Validate options against current GPT Image API constraints before sending."""
    if quality and quality not in VALID_QUALITIES:
        raise ValueError(f"quality 必须是 {sorted(VALID_QUALITIES)} 之一")
    if background and background not in VALID_BACKGROUNDS:
        raise ValueError(f"background 必须是 {sorted(VALID_BACKGROUNDS)} 之一")
    if fmt and fmt not in VALID_FORMATS:
        raise ValueError(f"format 必须是 {sorted(VALID_FORMATS)} 之一")

    if _is_gpt_image_2(model) and background == "transparent":
        raise ValueError("gpt-image-2 目前不支持 background=transparent；请改用 background=auto/opaque，或换支持透明背景的模型。")

    if output_compression is not None:
        if not 0 <= output_compression <= 100:
            raise ValueError("output_compression 必须在 0-100 之间")
        if fmt not in {"jpeg", "webp"}:
            raise ValueError("output_compression 只适用于 jpeg/webp；PNG 请不要设置 --compression")

    if not size or size == "auto":
        return

    m = re.match(r"^(\d+)x(\d+)$", size)
    if not m:
        raise ValueError("size 必须是 auto 或 <宽>x<高>，例如 1024x1024")
    width, height = int(m.group(1)), int(m.group(2))
    if width % 16 != 0 or height % 16 != 0:
        raise ValueError("size 的宽高都必须能被 16 整除")
    if max(width, height) > MAX_EDGE:
        raise ValueError(f"size 最长边不能超过 {MAX_EDGE}px")
    ratio = max(width, height) / min(width, height)
    if ratio > MAX_ASPECT_RATIO:
        raise ValueError("size 长短边比例不能超过 3:1")
    pixels = width * height
    if pixels < MIN_PIXELS or pixels > MAX_PIXELS:
        raise ValueError(f"size 总像素需在 {MIN_PIXELS:,}-{MAX_PIXELS:,} 之间")


# =============================================================================
# 数据模型
# =============================================================================
@dataclass
class GeneratedImage:
    """生成的图片结果"""
    index: int
    prompt: str
    b64_json: str
    revised_prompt: Optional[str] = None
    saved_path: Optional[str] = None
    file_size: int = 0

    @property
    def image_bytes(self) -> bytes:
        return base64.b64decode(self.b64_json)

    def save(self, filepath: str) -> str:
        with open(filepath, 'wb') as f:
            f.write(self.image_bytes)
        self.saved_path = filepath
        self.file_size = os.path.getsize(filepath)
        return filepath


@dataclass
class ImageGenConfig:
    """图片生成配置"""
    model: str = DEFAULT_MODEL
    size: Optional[str] = None
    quality: Optional[str] = None
    n: int = 1
    format: Optional[str] = None
    output_compression: Optional[int] = None
    background: Optional[str] = None
    moderation: Optional[str] = "low"
    response_format: str = "b64_json"
    user: Optional[str] = None
    timeout: int = DEFAULT_TIMEOUT
    outdir: str = DEFAULT_OUTDIR
    filename_prefix: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": "",
            "n": self.n,
            "response_format": self.response_format,
        }
        if self.size:
            payload["size"] = self.size
        if self.quality:
            payload["quality"] = self.quality
        if self.format:
            payload["format"] = self.format
        if self.output_compression is not None:
            payload["output_compression"] = self.output_compression
        if self.background:
            payload["background"] = self.background
        payload["moderation"] = self.moderation or "low"
        if self.user:
            payload["user"] = self.user
        return payload


@dataclass
class ImageEditConfig:
    """图片编辑配置"""
    model: str = DEFAULT_MODEL
    image: str = ""
    mask: Optional[str] = None
    refs: Optional[List[str]] = None
    size: Optional[str] = None
    quality: Optional[str] = None
    n: int = 1
    format: Optional[str] = None
    output_compression: Optional[int] = None
    background: Optional[str] = None
    moderation: Optional[str] = "low"
    response_format: str = "b64_json"
    user: Optional[str] = None
    timeout: int = DEFAULT_TIMEOUT
    outdir: str = DEFAULT_OUTDIR
    filename_prefix: Optional[str] = None


# =============================================================================
# URL / data URL 处理
# =============================================================================
def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _is_data_url(value: str) -> bool:
    return value.startswith("data:")


def _data_url_to_bytes(data_url: str) -> bytes:
    pattern = r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$"
    match = re.match(pattern, data_url, re.IGNORECASE)
    if not match:
        raise ValueError(f"无效的 data URL 格式")
    return base64.b64decode(match.group("data"))


def _prepare_image_source(value: str) -> str:
    """
    准备图片来源，返回本地文件路径。
    - 本地路径：直接返回
    - URL：下载到临时文件，返回临时路径
    - data URL：解码到临时文件，返回临时路径
    """
    import tempfile
    if _is_url(value):
        resp = _session.get(value, timeout=30)
        resp.raise_for_status()
        suffix = ".png"
        ct = resp.headers.get("content-type", "")
        if "jpeg" in ct or "jpg" in ct:
            suffix = ".jpg"
        elif "webp" in ct:
            suffix = ".webp"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(resp.content)
            return f.name
    if _is_data_url(value):
        data = _data_url_to_bytes(value)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(data)
            return f.name
    if not os.path.exists(value):
        raise ValueError(f"图片文件不存在: {value}")
    return value


def _download_url(url: str) -> bytes:
    """从 URL 下载图片，返回 bytes"""
    resp = _session.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def _guess_mime(filepath: str) -> str:
    """猜测图片 MIME type"""
    mime, _ = mimetypes.guess_type(filepath)
    if mime and mime.startswith("image/"):
        return mime
    ext = os.path.splitext(filepath)[1].lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "image/png")


# =============================================================================
# Mask 校验与修复
# =============================================================================

def _validate_or_fix_mask(image_path: str, mask_path: str, fix: bool = False) -> Optional[str]:
    """Validate mask dimensions/alpha. If fix=True, add alpha from grayscale mask when possible."""
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("mask 预检需要 Pillow：请安装 pillow，或不要使用 --validate-mask/--fix-mask-alpha")

    resolved_image = _prepare_image_source(image_path)
    resolved_mask = _prepare_image_source(mask_path)
    try:
        image = Image.open(resolved_image)
        mask = Image.open(resolved_mask)
        if image.size != mask.size:
            raise ValueError(f"mask 尺寸必须与原图一致：image={image.size}, mask={mask.size}")
        if mask.format and image.format and mask.format != image.format:
            print(f"    [⚠️] mask 格式 {mask.format} 与原图 {image.format} 不一致，官方要求同格式；兼容 provider 可能仍接受。", file=sys.stderr)
        has_alpha = mask.mode in ("RGBA", "LA") or (mask.mode == "P" and "transparency" in mask.info)
        if has_alpha:
            return resolved_mask
        if not fix:
            raise ValueError("mask 必须包含 alpha channel；可加 --fix-mask-alpha 自动把灰度 mask 转为 RGBA alpha mask")
        mask_l = mask.convert("L")
        mask_rgba = mask_l.convert("RGBA")
        mask_rgba.putalpha(mask_l)
        fixed_path = os.path.splitext(resolved_mask)[0] + "_alpha.png"
        mask_rgba.save(fixed_path, format="PNG")
        print(f"    [mask] 已生成 alpha mask: {fixed_path}", file=sys.stderr)
        return fixed_path
    finally:
        if resolved_image != image_path and os.path.exists(resolved_image):
            os.unlink(resolved_image)


# =============================================================================
# 诊断工具
# =============================================================================
def _request_diagnostic(resp: _requests.Response) -> str:
    """构建详细的请求诊断信息"""
    parts = [
        f"HTTP {resp.status_code}",
        f"Content-Type: {resp.headers.get('content-type', 'unknown')}",
    ]
    # 追踪 ID
    req_id = resp.headers.get("x-request-id") or resp.headers.get("request-id")
    if req_id:
        parts.append(f"Request-ID: {req_id}")
    cf_ray = resp.headers.get("cf-ray")
    if cf_ray:
        parts.append(f"CF-Ray: {cf_ray}")
    return " | ".join(parts)


def _is_html_error(resp: _requests.Response) -> Optional[str]:
    """检测 HTML 错误页面（网关错误/反爬拦截）"""
    ct = resp.headers.get("content-type", "").lower()
    if "text/html" in ct and resp.status_code >= 400:
        return f"服务端返回 HTML 而非 JSON（可能是网关错误页面或反爬拦截）"
    return None


# =============================================================================
# 核心请求函数
# =============================================================================
def _request_json(
    endpoint: str,
    payload: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """发送 JSON 请求（用于 /images/generations）"""
    base_url, _ = ensure_runtime_config()
    request_id = str(uuid.uuid4())[:8]
    url = f"{base_url}{endpoint}"

    try:
        resp = _session.post(
            url,
            json=payload,
            timeout=timeout,
            headers={"X-Client-Request-Id": request_id},
        )
    except _requests.exceptions.Timeout:
        return {"_error": f"请求超时 ({timeout}s)", "_request_id": request_id}
    except _requests.exceptions.ConnectionError as e:
        return {"_error": f"连接失败: {e}", "_request_id": request_id}
    except Exception as e:
        return {"_error": str(e), "_request_id": request_id}

    # 检查 HTML 错误
    html_err = _is_html_error(resp)
    if html_err:
        return {"_error": f"{html_err} | {_request_diagnostic(resp)}", "_request_id": request_id}

    # 解析 JSON
    try:
        data = resp.json()
    except Exception:
        return {
            "_error": f"JSON 解析失败 | {_request_diagnostic(resp)} | 响应前200字符: {resp.text[:200]}",
            "_request_id": request_id,
        }

    # 非 2xx
    if resp.status_code >= 400:
        err_msg = data.get("error", {}).get("message", str(data)) if isinstance(data.get("error"), dict) else str(data)
        return {"_error": f"HTTP {resp.status_code}: {err_msg[:200]}", "_request_id": request_id}

    return data


def _request_multipart(
    endpoint: str,
    prompt: str,
    image_path: str,
    extra_image_paths: Optional[List[str]] = None,
    mask_path: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    size: Optional[str] = None,
    quality: Optional[str] = None,
    n: int = 1,
    fmt: Optional[str] = None,
    output_compression: Optional[int] = None,
    background: Optional[str] = None,
    response_format: str = "b64_json",
    timeout: int = DEFAULT_TIMEOUT,
    moderation: Optional[str] = None,
) -> Dict[str, Any]:
    """发送 multipart 请求（用于 /images/edits）"""
    base_url, _ = ensure_runtime_config()
    request_id = str(uuid.uuid4())[:8]
    url = f"{base_url}{endpoint}"

    _validate_image_options(
        model=model,
        size=size,
        quality=quality,
        fmt=fmt,
        output_compression=output_compression,
        background=background,
    )

    # 解析图片来源
    try:
        resolved_image = _prepare_image_source(image_path)
    except ValueError as e:
        return {"_error": str(e)}

    resolved_extra_images: List[str] = []
    for value in extra_image_paths or []:
        try:
            resolved_extra_images.append(_prepare_image_source(value))
        except ValueError as e:
            return {"_error": str(e)}

    resolved_mask = None
    if mask_path:
        try:
            resolved_mask = _prepare_image_source(mask_path)
        except ValueError as e:
            return {"_error": str(e)}

    # 构建 multipart fields（list-of-tuples，支持同名 image[] 多字段）
    files: List[Tuple[str, Any]] = [
        ("model", (None, model)),
        ("prompt", (None, prompt)),
        ("n", (None, str(n))),
        ("response_format", (None, response_format)),
    ]

    # 图片文件（使用具体 MIME type，部分 provider 不接受 application/octet-stream）
    all_images = [resolved_image, *resolved_extra_images]
    image_field = "image[]" if len(all_images) > 1 else "image"
    for item in all_images:
        image_filename = os.path.basename(item)
        files.append((image_field, (image_filename, open(item, "rb"), _guess_mime(item))))

    if resolved_mask:
        mask_filename = os.path.basename(resolved_mask)
        files.append(("mask", (mask_filename, open(resolved_mask, "rb"), _guess_mime(resolved_mask))))

    # 可选参数
    if size:
        files.append(("size", (None, size)))
    if quality:
        files.append(("quality", (None, quality)))
    if fmt:
        files.append(("format", (None, fmt)))
    if output_compression is not None:
        files.append(("output_compression", (None, str(output_compression))))
    if background:
        files.append(("background", (None, background)))
    if moderation:
        files.append(("moderation", (None, moderation)))

    try:
        resp = _session.post(
            url,
            files=files,
            timeout=timeout,
            headers={"X-Client-Request-Id": request_id},
        )
    except _requests.exceptions.Timeout:
        return {"_error": f"请求超时 ({timeout}s)", "_request_id": request_id}
    except _requests.exceptions.ConnectionError as e:
        return {"_error": f"连接失败: {e}", "_request_id": request_id}
    except Exception as e:
        return {"_error": str(e), "_request_id": request_id}
    finally:
        # 关闭文件句柄
        for _, v in files:
            if isinstance(v, tuple) and len(v) >= 2 and hasattr(v[1], "close"):
                v[1].close()
        # 清理临时文件
        if resolved_image != image_path and os.path.exists(resolved_image):
            os.unlink(resolved_image)
        if resolved_mask and resolved_mask != mask_path and os.path.exists(resolved_mask):
            os.unlink(resolved_mask)
        for original, resolved in zip(extra_image_paths or [], resolved_extra_images):
            if resolved != original and os.path.exists(resolved):
                os.unlink(resolved)

    # 检查 HTML 错误
    html_err = _is_html_error(resp)
    if html_err:
        return {"_error": f"{html_err} | {_request_diagnostic(resp)}", "_request_id": request_id}

    # 解析 JSON
    try:
        data = resp.json()
    except Exception:
        return {
            "_error": f"JSON 解析失败 | {_request_diagnostic(resp)} | 响应前200字符: {resp.text[:200]}",
            "_request_id": request_id,
        }

    # 非 2xx
    if resp.status_code >= 400:
        err_msg = data.get("error", {}).get("message", str(data)) if isinstance(data.get("error"), dict) else str(data)
        return {"_error": f"HTTP {resp.status_code}: {err_msg[:200]}", "_request_id": request_id}

    return data


def _parse_error(resp: Dict[str, Any]) -> Optional[str]:
    if "_error" in resp:
        return resp["_error"]
    err = resp.get("error")
    if err is not None:
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        return msg[:200]
    return None


def _save_images(resp: Dict[str, Any], prompt: str, outdir: str, prefix: Optional[str] = None, expected_n: int = 1) -> List[GeneratedImage]:
    results = []
    timestamp = time.strftime("%m%d_%H%M%S")
    safe_prompt = "".join(c if c.isalnum() or c in "_-" or '\u4e00' <= c <= '\u9fff' else "_" for c in prompt[:30])
    base_name = prefix or f"{timestamp}_{safe_prompt}"

    data = resp.get("data", [])
    actual_count = len(data)
    if expected_n > 1 and actual_count != expected_n:
        print(f"    [⚠️] 请求 n={expected_n}，实际返回 {actual_count} 张（参数被上游限制）")

    for i, item in enumerate(data):
        b64 = item.get("b64_json", "")
        url = item.get("url", "")

        if b64:
            # b64_json 格式
            img_bytes = base64.b64decode(b64)
            ext = _detect_format(img_bytes)
            img = GeneratedImage(
                index=i,
                prompt=prompt,
                b64_json=b64,
                revised_prompt=item.get("revised_prompt"),
            )
            filepath = os.path.join(outdir, f"{base_name}_{i}.{ext}")
            img.save(filepath)
            results.append(img)
        elif url:
            # url 格式 — 从远程下载
            try:
                print(f"    [⬇️] 从 URL 下载图片 {i}...", file=sys.stderr)
                img_bytes = _download_url(url)
                ext = _detect_format(img_bytes)
                filepath = os.path.join(outdir, f"{base_name}_{i}.{ext}")
                with open(filepath, 'wb') as f:
                    f.write(img_bytes)
                img = GeneratedImage(
                    index=i,
                    prompt=prompt,
                    b64_json="",  # url 模式没有 b64
                    revised_prompt=item.get("revised_prompt"),
                )
                img.saved_path = filepath
                img.file_size = os.path.getsize(filepath)
                results.append(img)
            except Exception as e:
                print(f"    [⚠️] 下载图片 {i} 失败: {e}", file=sys.stderr)
        else:
            continue

    return results


def _detect_format(img_bytes: bytes) -> str:
    if img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "png"
    if img_bytes[:2] == b'\xff\xd8':
        return "jpeg"
    if img_bytes[:4] == b'RIFF' and len(img_bytes) > 12 and img_bytes[8:12] == b'WEBP':
        return "webp"
    return "png"


def _is_retryable_error(error_msg: str) -> bool:
    """判断是否为可重试的临时错误"""
    retryable_patterns = [
        "Upstream request failed",
        "stream disconnected",
        "connection reset",
        "timeout",
        "连接失败",
        "429",
        "502",
        "503",
        "504",
    ]
    msg_lower = error_msg.lower()
    return any(p.lower() in msg_lower for p in retryable_patterns)


def _sleep_with_countdown(seconds: int, label: str = "重试") -> None:
    """带提示的等待"""
    print(f"    ⏳ {label}等待 {seconds} 秒...", file=sys.stderr)
    time.sleep(seconds)


# =============================================================================
# 主要 API 函数（带重试）
# =============================================================================
def generate(
    prompt: str,
    config: Optional[ImageGenConfig] = None,
    silent: bool = False,
) -> List[GeneratedImage]:
    if config is None:
        config = ImageGenConfig()

    os.makedirs(config.outdir, exist_ok=True)

    _validate_image_options(
        model=config.model,
        size=config.size,
        quality=config.quality,
        fmt=config.format,
        output_compression=config.output_compression,
        background=config.background,
    )

    payload = config.to_payload()
    payload["prompt"] = prompt

    if not silent:
        print(f"[生成] {prompt[:50]}...")
        print(f"    参数: size={config.size or 'default'} quality={config.quality or 'default'} n={config.n}")

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            _sleep_with_countdown(RETRY_DELAY, f"第{attempt}次重试")

        start = time.time()
        resp = _request_json("/images/generations", payload, timeout=config.timeout)
        elapsed = time.time() - start

        if not silent:
            print(f"    端点: {ensure_runtime_config()[0]}")

        err = _parse_error(resp)
        if err:
            last_error = err
            if attempt < MAX_RETRIES and _is_retryable_error(err):
                print(f"    [⚠️] 第{attempt + 1}次失败: {err}，将重试...", file=sys.stderr)
                continue
            else:
                raise RuntimeError(f"生成失败: {err}")

        # 成功
        images = _save_images(resp, prompt, config.outdir, config.filename_prefix, expected_n=config.n)
        if not images:
            raise RuntimeError("响应中没有图片数据")

        total_kb = sum(img.file_size for img in images) // 1024
        if not silent:
            retry_info = f"（第{attempt + 1}次尝试）" if attempt > 0 else ""
            print(f"[✅] 成功生成 {len(images)} 张图片，共 {total_kb}KB，耗时 {elapsed:.1f}s{retry_info}")
            for img in images:
                print(f"    → {img.saved_path} ({img.file_size // 1024}KB)")
                if img.revised_prompt:
                    print(f"      修订: {img.revised_prompt[:60]}...")

        return images

    # 所有重试都失败
    raise RuntimeError(f"生成失败（已重试{MAX_RETRIES}次）: {last_error}")


def edit(
    prompt: str,
    image: str,
    mask: Optional[str] = None,
    config: Optional[ImageEditConfig] = None,
    silent: bool = False,
) -> List[GeneratedImage]:
    if config is None:
        config = ImageEditConfig()

    os.makedirs(config.outdir, exist_ok=True)

    if not silent:
        print(f"[编辑] {prompt[:50]}...")
        print(f"    原图: {image}")
        if config.refs:
            print(f"    参考图: {len(config.refs)} 张")
        if mask:
            print(f"    mask: {mask}")
        print(f"    参数: size={config.size or 'default'} quality={config.quality or 'default'}")

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            _sleep_with_countdown(RETRY_DELAY, f"第{attempt}次重试")

        start = time.time()
        resp = _request_multipart(
            "/images/edits",
            prompt=prompt,
            image_path=image,
            extra_image_paths=config.refs,
            mask_path=mask,
            model=config.model,
            size=config.size,
            quality=config.quality,
            n=config.n,
            fmt=config.format,
            output_compression=config.output_compression,
            background=config.background,
            response_format=config.response_format,
            timeout=config.timeout,
            moderation=config.moderation,
        )
        elapsed = time.time() - start

        if not silent:
            print(f"    端点: {ensure_runtime_config()[0]}")

        err = _parse_error(resp)
        if err:
            last_error = err
            if attempt < MAX_RETRIES and _is_retryable_error(err):
                print(f"    [⚠️] 第{attempt + 1}次失败: {err}，将重试...", file=sys.stderr)
                continue
            else:
                raise RuntimeError(f"编辑失败: {err}")

        # 成功
        images = _save_images(resp, prompt, config.outdir, config.filename_prefix, expected_n=config.n)
        if not images:
            raise RuntimeError("响应中没有图片数据")

        total_kb = sum(img.file_size for img in images) // 1024
        if not silent:
            retry_info = f"（第{attempt + 1}次尝试）" if attempt > 0 else ""
            print(f"[✅] 成功编辑 {len(images)} 张图片，共 {total_kb}KB，耗时 {elapsed:.1f}s{retry_info}")
            for img in images:
                print(f"    → {img.saved_path} ({img.file_size // 1024}KB)")
                if img.revised_prompt:
                    print(f"      修订: {img.revised_prompt[:60]}...")

        return images

    # 所有重试都失败
    raise RuntimeError(f"编辑失败（已重试{MAX_RETRIES}次）: {last_error}")


# =============================================================================
# 快捷函数
# =============================================================================
def quick_generate(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "low",
    n: int = 1,
    outdir: str = DEFAULT_OUTDIR,
) -> List[GeneratedImage]:
    config = ImageGenConfig(size=size, quality=quality, n=n, outdir=outdir)
    return generate(prompt, config)


def quick_edit(
    prompt: str,
    image: str,
    mask: Optional[str] = None,
    size: str = "1024x1024",
    outdir: str = DEFAULT_OUTDIR,
) -> List[GeneratedImage]:
    config = ImageEditConfig(image=image, mask=mask, size=size, outdir=outdir)
    return edit(prompt, image, mask, config)


# =============================================================================
# CLI 入口
# =============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Image API 图片生成与编辑",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
环境变量:
  IMAGE_API_BASE  API 端点 (必须)
  IMAGE_API_KEY   API 密钥 (必须)
  IMAGE_OUT_DIR   输出目录 (默认 /tmp/gptimage)
  IMAGE_MODEL     默认模型 (默认 gpt-image-2)

示例:
  普通模式:
    python3 image_api.py "A beautiful sunset" --size 1536x1024 --quality high
    python3 image_api.py "Make it green" --edit --image source.png
    python3 image_api.py "Add a red hat" --edit --image source.png --mask mask.png

  多参考图编辑:
    python3 image_api.py "Combine" --edit --image main.png --ref ref1.png --ref ref2.png

  URL / data URL 编辑:
    python3 image_api.py "Make it blue" --edit --image https://example.com/img.png
    python3 image_api.py "Change style" --edit --image "data:image/png;base64,...."

  JSON 输出模式:
    python3 image_api.py "A cat" --size 1024x1024 --json
    python3 image_api.py "A flower" --n 4 --json
        """
    )
    parser.add_argument("prompt", help="图片描述 / 编辑描述")
    parser.add_argument("--edit", action="store_true", help="使用 edits 端点（编辑模式）")
    parser.add_argument("--image", help="原图路径/URL/data URL（编辑模式必填）")
    parser.add_argument("--ref", dest="refs", action="append", default=[], help="参考图，可重复传入；--edit 下作为额外 image[]")
    parser.add_argument("--mask", help="mask 路径/URL/data URL（可选）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型名称 (默认 {DEFAULT_MODEL})")
    parser.add_argument("--size", default="1024x1024", help="尺寸，默认 1024x1024；也支持 auto 与符合约束的任意 16 倍数尺寸")
    parser.add_argument("--quality", default="low", choices=["low", "medium", "high", "auto"], help="质量 (low/medium/high/auto)")
    parser.add_argument("--n", type=int, default=1, help="生成数量 1-10（实际上游始终只返回 1）")
    parser.add_argument("--format", dest="fmt", choices=["png", "jpeg", "webp"], help="输出格式")
    parser.add_argument("--compression", type=int, help="压缩率 0-100（仅 jpeg/webp）")
    parser.add_argument("--background", choices=["opaque", "auto", "transparent"], help="背景")
    parser.add_argument("--moderation", choices=["auto", "low"], default="low", help="审核级别，默认 low")
    parser.add_argument("--outdir", "-o", default=DEFAULT_OUTDIR, help="输出目录")
    parser.add_argument("--prefix", help="文件名前缀")
    parser.add_argument("--timeout", type=int, default=900, help="超时秒数")
    parser.add_argument("--validate-mask", action="store_true", help="编辑前检查 mask 尺寸/alpha")
    parser.add_argument("--fix-mask-alpha", action="store_true", help="mask 无 alpha 时自动转为 RGBA alpha mask（需要 Pillow）")
    parser.add_argument("--json", action="store_true", help="JSON 结构化输出模式（用于程序化调用）")

    args = parser.parse_args()

    # 参数验证
    if args.edit and not args.image:
        err = "编辑模式必须指定 --image"
        if args.json:
            print(json.dumps({"ok": False, "error": err}, ensure_ascii=False))
        else:
            print(f"[❌] {err}")
        sys.exit(1)

    # Mask 预检
    if args.edit and args.mask and (args.validate_mask or args.fix_mask_alpha):
        try:
            args.mask = _validate_or_fix_mask(args.image, args.mask, fix=args.fix_mask_alpha)
        except Exception as e:
            if args.json:
                print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
            else:
                print(f"[❌] {e}")
            sys.exit(1)

    # 构建配置
    if args.edit:
        config = ImageEditConfig(
            model=args.model,
            image=args.image,
            mask=args.mask,
            refs=args.refs if args.refs else None,
            size=args.size,
            quality=args.quality,
            n=args.n,
            format=args.fmt,
            output_compression=args.compression,
            background=args.background,
            moderation=args.moderation,
            timeout=args.timeout,
            outdir=args.outdir,
            filename_prefix=args.prefix,
        )
    else:
        config = ImageGenConfig(
            model=args.model,
            size=args.size,
            quality=args.quality,
            n=args.n,
            format=args.fmt,
            output_compression=args.compression,
            background=args.background,
            moderation=args.moderation,
            timeout=args.timeout,
            outdir=args.outdir,
            filename_prefix=args.prefix,
        )

    try:
        if args.edit:
            images = edit(args.prompt, args.image, args.mask, config, silent=args.json)
        else:
            images = generate(args.prompt, config, silent=args.json)

        if args.json:
            result = {
                "ok": True,
                "paths": [img.saved_path for img in images if img.saved_path],
                "used_params": {
                    "mode": "edit" if args.edit else "generate",
                    "model": args.model,
                    "size": args.size,
                    "quality": args.quality,
                    "output_format": args.fmt or "png",
                    "n": args.n,
                    "moderation": args.moderation or "low",
                },
                "endpoint": ensure_runtime_config()[0],
            }
            print(json.dumps(result, ensure_ascii=False))
        else:
            for img in images:
                print(f"  → {img.saved_path}")

    except Exception as e:
        if args.json:
            print(json.dumps({"ok": False, "error": str(e), "endpoint": API_BASE or ""}, ensure_ascii=False))
        else:
            print(f"[❌] 失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
