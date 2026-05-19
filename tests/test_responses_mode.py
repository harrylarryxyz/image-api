import base64
import importlib.util
import os
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "image_api.py"
spec = importlib.util.spec_from_file_location("image_api_script", MODULE_PATH)
image_api = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = image_api
spec.loader.exec_module(image_api)


def png_b64():
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode("ascii")


def reset_config(monkeypatch):
    image_api.API_BASE = None
    image_api.API_KEY = None
    monkeypatch.setenv("IMAGE_API_BASE", "https://api.example.test/v1")
    monkeypatch.setenv("IMAGE_API_KEY", "test-key")
    monkeypatch.delenv("IMAGE_API_MODE", raising=False)


def test_resolve_api_mode_auto_uses_images_for_normal_base(monkeypatch):
    reset_config(monkeypatch)
    assert image_api.resolve_api_mode("auto") == "images"


def test_resolve_api_mode_auto_corrects_responses_url(monkeypatch):
    image_api.API_BASE = None
    image_api.API_KEY = None
    monkeypatch.setenv("IMAGE_API_BASE", "https://api.example.test/v1/responses")
    monkeypatch.setenv("IMAGE_API_KEY", "test-key")
    mode = image_api.resolve_api_mode("auto")
    assert mode == "responses"
    assert image_api.ensure_runtime_config()[0] == "https://api.example.test/v1"


def test_responses_generate_posts_to_responses_and_saves_image(monkeypatch, tmp_path):
    reset_config(monkeypatch)
    captured = {}

    def fake_request_json(endpoint, payload, timeout):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {
            "output": [
                {
                    "type": "image_generation_call",
                    "result": png_b64(),
                    "revised_prompt": "revised",
                    "output_format": "png",
                    "action": "generate",
                }
            ]
        }

    monkeypatch.setattr(image_api, "_request_json", fake_request_json)
    cfg = image_api.ImageGenConfig(model="gpt-5.5", size="1024x1024", quality="medium", format="png", outdir=str(tmp_path), api_mode="responses")

    images = image_api.generate("draw a star", cfg, silent=True)

    assert captured["endpoint"] == "/responses"
    assert captured["payload"]["input"] == "draw a star"
    tool = captured["payload"]["tools"][0]
    assert tool["type"] == "image_generation"
    assert tool["size"] == "1024x1024"
    assert tool["quality"] == "medium"
    assert tool["output_format"] == "png"
    assert "prompt" not in captured["payload"]
    assert len(images) == 1
    assert Path(images[0].saved_path).exists()


def test_responses_edit_uses_input_images_refs_and_mask_object(monkeypatch, tmp_path):
    reset_config(monkeypatch)
    main = tmp_path / "main.png"
    ref = tmp_path / "ref.png"
    mask = tmp_path / "mask.png"
    for p in [main, ref, mask]:
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    captured = {}

    def fake_request_json(endpoint, payload, timeout):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {"output": [{"type": "image_generation_call", "result": png_b64(), "action": "edit"}]}

    monkeypatch.setattr(image_api, "_request_json", fake_request_json)
    cfg = image_api.ImageEditConfig(model="gpt-5.5", image=str(main), refs=[str(ref)], mask=str(mask), outdir=str(tmp_path), api_mode="responses")

    images = image_api.edit("make it blue", str(main), str(mask), cfg, silent=True)

    assert captured["endpoint"] == "/responses"
    content = captured["payload"]["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "make it blue"}
    assert [item["type"] for item in content[1:]] == ["input_image", "input_image"]
    tool = captured["payload"]["tools"][0]
    assert tool["input_image_mask"] == {"image_url": tool["input_image_mask"]["image_url"]}
    assert tool["input_image_mask"]["image_url"].startswith("data:image/png;base64,")
    assert len(images) == 1


def test_images_mode_keeps_original_images_endpoint(monkeypatch, tmp_path):
    reset_config(monkeypatch)
    captured = {}

    def fake_request_json(endpoint, payload, timeout):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {"data": [{"b64_json": png_b64()}]}

    monkeypatch.setattr(image_api, "_request_json", fake_request_json)
    cfg = image_api.ImageGenConfig(model="gpt-image-2", outdir=str(tmp_path), api_mode="images")

    image_api.generate("draw a cat", cfg, silent=True)

    assert captured["endpoint"] == "/images/generations"
    assert captured["payload"]["prompt"] == "draw a cat"
    assert "tools" not in captured["payload"]


def test_auto_generate_falls_back_to_responses_when_images_endpoint_missing(monkeypatch, tmp_path):
    reset_config(monkeypatch)
    calls = []

    def fake_request_json(endpoint, payload, timeout):
        calls.append((endpoint, payload))
        if endpoint == "/images/generations":
            return {"_error": "HTTP 404: {'error': 'not found'}"}
        return {"output": [{"type": "image_generation_call", "result": png_b64(), "action": "generate"}]}

    monkeypatch.setattr(image_api, "_request_json", fake_request_json)
    cfg = image_api.ImageGenConfig(model="gpt-5.5", outdir=str(tmp_path), api_mode="auto")

    images = image_api.generate("draw a fallback star", cfg, silent=True)

    assert [c[0] for c in calls] == ["/images/generations", "/responses"]
    assert calls[1][1]["tools"][0]["type"] == "image_generation"
    assert len(images) == 1


def test_auto_generate_does_not_fallback_on_auth_error(monkeypatch, tmp_path):
    reset_config(monkeypatch)

    def fake_request_json(endpoint, payload, timeout):
        return {"_error": "HTTP 401: invalid api key"}

    monkeypatch.setattr(image_api, "_request_json", fake_request_json)
    cfg = image_api.ImageGenConfig(model="gpt-5.5", outdir=str(tmp_path), api_mode="auto")

    with pytest.raises(RuntimeError, match="401"):
        image_api.generate("draw", cfg, silent=True)
