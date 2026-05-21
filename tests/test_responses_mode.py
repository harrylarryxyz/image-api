import base64
import importlib.util
import json
import os
import subprocess
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
    cfg = image_api.ImageGenConfig(model="responses-test-model", size="1024x1024", quality="medium", format="png", outdir=str(tmp_path), api_mode="responses")

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
    cfg = image_api.ImageEditConfig(model="responses-test-model", image=str(main), refs=[str(ref)], mask=str(mask), outdir=str(tmp_path), api_mode="responses")

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
    cfg = image_api.ImageGenConfig(model="images-test-model", outdir=str(tmp_path), api_mode="images")

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
    cfg = image_api.ImageGenConfig(model="responses-test-model", outdir=str(tmp_path), api_mode="auto")

    images = image_api.generate("draw a fallback star", cfg, silent=True)

    assert [c[0] for c in calls] == ["/images/generations", "/responses"]
    assert calls[1][1]["tools"][0]["type"] == "image_generation"
    assert len(images) == 1


def test_auto_generate_does_not_fallback_on_auth_error(monkeypatch, tmp_path):
    reset_config(monkeypatch)

    def fake_request_json(endpoint, payload, timeout):
        return {"_error": "HTTP 401: invalid api key"}

    monkeypatch.setattr(image_api, "_request_json", fake_request_json)
    cfg = image_api.ImageGenConfig(model="responses-test-model", outdir=str(tmp_path), api_mode="auto")

    with pytest.raises(RuntimeError, match="401"):
        image_api.generate("draw", cfg, silent=True)


def test_validate_image_options_requires_model():
    with pytest.raises(ValueError, match="IMAGE_MODEL"):
        image_api._validate_image_options(model="", size="1024x1024")


def test_responses_edit_rejects_missing_model_before_request(monkeypatch, tmp_path):
    reset_config(monkeypatch)
    main = tmp_path / "main.png"
    main.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    def fail_request(*args, **kwargs):
        raise AssertionError("request should not be sent without a model")

    monkeypatch.setattr(image_api, "_request_json", fail_request)
    cfg = image_api.ImageEditConfig(model="", image=str(main), outdir=str(tmp_path), api_mode="responses")

    with pytest.raises(ValueError, match="IMAGE_MODEL"):
        image_api.edit("make it blue", str(main), config=cfg, silent=True)


def test_error_sanitization_redacts_env_and_explicit_model(monkeypatch):
    env_model = "PRIVATE_ENV_MODEL_SHOULD_NOT_APPEAR"
    explicit_model = "PRIVATE_EXPLICIT_MODEL_SHOULD_NOT_APPEAR"
    monkeypatch.setenv("IMAGE_MODEL", env_model)
    message = f"model {env_model} rejected; fallback {explicit_model} failed; Bearer token-value"

    sanitized = image_api._sanitize_runtime_message(message, [explicit_model])

    assert env_model not in sanitized
    assert explicit_model not in sanitized
    assert "Bearer <redacted>" in sanitized


def test_parse_error_redacts_model_from_provider_error():
    explicit_model = "PRIVATE_PROVIDER_MODEL_SHOULD_NOT_APPEAR"
    err = image_api._parse_error({"error": {"message": f"unknown model {explicit_model}"}}, [explicit_model])

    assert explicit_model not in err
    assert "<redacted>" in err


def test_cli_help_does_not_expose_env_model_value():
    env = os.environ.copy()
    private_model = "PRIVATE_PROVIDER_MODEL_SHOULD_NOT_APPEAR"
    env["IMAGE_MODEL"] = private_model
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, "-B", str(MODULE_PATH), "--help"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0
    assert private_model not in combined


def test_cli_json_error_without_model_has_no_endpoint(monkeypatch):
    env = os.environ.copy()
    env["IMAGE_API_BASE"] = "https://api.example.test/v1"
    env["IMAGE_API_KEY"] = "test-key"
    env.pop("IMAGE_MODEL", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, "-B", str(MODULE_PATH), "--json", "draw a cat"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    data = json.loads(result.stdout)
    assert result.returncode == 1
    assert data["ok"] is False
    assert "IMAGE_MODEL" in data["error"]
    assert "endpoint" not in data
