"""
Unit test suite for services/image_generator.py using pytest and mocked InferenceClient.
Covers:
- Success case
- Missing token
- Auth / Permission error (401 & 403)
- Rate limit (429 with retry)
- Timeout error (with retry)
- Empty / whitespace prompt validation
- Aspect ratio mapping
- Negative prompt graceful degradation (422)
- Groq prompt enhancer
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from PIL import Image
import huggingface_hub.errors as hf_errors

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.image_generator import (
    ASPECT_RATIO_MAP,
    STYLE_PRESETS,
    ImageGenerationResult,
    apply_style_preset,
    enhance_image_prompt,
    generate_image,
    validate_prompt,
)


@pytest.fixture
def dummy_image():
    """Create a simple test image in memory."""
    return Image.new("RGB", (1024, 1024), color="blue")


def _create_mock_hf_http_error(status_code: int, message: str) -> hf_errors.HfHubHTTPError:
    """Helper to construct valid HfHubHTTPError with a real httpx.Response."""
    req = httpx.Request("POST", "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell")
    res = httpx.Response(status_code=status_code, headers={"x-request-id": "req-12345"}, request=req)
    return hf_errors.HfHubHTTPError(message, response=res)


def test_empty_prompt():
    """Test validation failure on empty prompt."""
    res_empty = generate_image(prompt="")
    assert not res_empty.is_success
    assert "Prompt cannot be empty" in (res_empty.error or "")

    res_spaces = generate_image(prompt="   \n\t  ")
    assert not res_spaces.is_success
    assert "Prompt cannot be empty" in (res_spaces.error or "")


def test_missing_token():
    """Test behavior when HF_TOKEN is missing in HF mode."""
    with patch("services.image_generator.get_hf_token", side_effect=RuntimeError("HF_TOKEN is not configured")):
        res = generate_image(prompt="A futuristic electric car", provider="hf")
        assert not res.is_success
        assert "HF_TOKEN is not configured" in (res.error or "")


def test_missing_token_auto_fallback_to_free(dummy_image, tmp_path):
    """Test that missing HF token seamlessly uses free provider in auto mode."""
    with patch("services.image_generator.is_cloudflare_configured", return_value=False):
        with patch("services.image_generator.get_hf_token", side_effect=RuntimeError("HF_TOKEN is not configured")):
            with patch("services.image_generator.generate_image_free_provider", return_value=dummy_image):
                with patch("services.image_generator.IMAGES_DIR", tmp_path):
                    res = generate_image(prompt="A futuristic electric car", provider="auto")
                    assert res.is_success
                    assert res.model_used == "FLUX (Free Engine)"
                    assert "HF_TOKEN was not configured" in (res.warning or "")


def test_successful_image_generation(dummy_image, tmp_path):
    """Test successful image generation and file saving."""
    mock_client = MagicMock()
    mock_client.text_to_image.return_value = dummy_image

    with patch("services.image_generator.get_hf_token", return_value="hf_dummy_token"):
        with patch("services.image_generator.IMAGES_DIR", tmp_path):
            result = generate_image(
                prompt="A majestic lion on a savanna rock",
                style="cinematic",
                aspect_ratio="16:9",
                client=mock_client
            )

    assert result.is_success
    assert result.image is not None
    assert result.image_path is not None
    assert Path(result.image_path).exists()
    assert result.width == 1024
    assert result.height == 576
    assert result.model_used == "black-forest-labs/FLUX.1-schnell"

    # Verify text_to_image arguments
    mock_client.text_to_image.assert_called_once()
    call_args, call_kwargs = mock_client.text_to_image.call_args
    assert "cinematic lighting" in call_args[0]
    assert call_kwargs["width"] == 1024
    assert call_kwargs["height"] == 576


def test_auth_error_no_retry():
    """Test that auth/permission errors (401, 403) fail immediately without retries."""
    mock_client = MagicMock()
    auth_err = _create_mock_hf_http_error(
        403,
        "403 Forbidden: This authentication method does not have sufficient permissions to call Inference Providers"
    )
    mock_client.text_to_image.side_effect = auth_err

    with patch("services.image_generator.get_hf_token", return_value="hf_dummy_token"):
        with patch("time.sleep") as mock_sleep:
            result = generate_image(
                prompt="A beautiful sunset",
                client=mock_client
            )

    assert not result.is_success
    assert "permission error (403 Forbidden)" in (result.error or "")
    # Auth errors should not retry
    assert mock_client.text_to_image.call_count == 1
    mock_sleep.assert_not_called()


def test_rate_limit_with_retries():
    """Test that 429 rate limit errors trigger exponential backoff retry up to max_retries."""
    mock_client = MagicMock()
    rate_limit_err = _create_mock_hf_http_error(429, "Rate limit reached")
    mock_client.text_to_image.side_effect = rate_limit_err

    with patch("services.image_generator.get_hf_token", return_value="hf_dummy_token"):
        with patch("time.sleep") as mock_sleep:
            result = generate_image(
                prompt="A cybernetic astronaut",
                client=mock_client
            )

    assert not result.is_success
    assert "rate limit exceeded" in (result.error or "").lower()
    # 1 initial attempt + 2 retries = 3 attempts
    assert mock_client.text_to_image.call_count == 3
    assert mock_sleep.call_count == 2


def test_timeout_with_retries():
    """Test that timeouts trigger retry and report clear message."""
    mock_client = MagicMock()
    timeout_err = httpx.ReadTimeout("Connection timed out waiting for server")
    mock_client.text_to_image.side_effect = timeout_err

    with patch("services.image_generator.get_hf_token", return_value="hf_dummy_token"):
        with patch("time.sleep") as mock_sleep:
            result = generate_image(
                prompt="Modern architectural villa",
                client=mock_client
            )

    assert not result.is_success
    assert "timed out" in (result.error or "").lower()
    assert mock_client.text_to_image.call_count == 3
    assert mock_sleep.call_count == 2


def test_negative_prompt_graceful_degradation(dummy_image, tmp_path):
    """Test graceful fallback when a model rejects negative_prompt with 422."""
    mock_client = MagicMock()
    unsupported_err = _create_mock_hf_http_error(
        422,
        "Unprocessable Entity: negative_prompt is not supported for this pipeline"
    )

    # First call with negative_prompt fails with 422, second call succeeds without negative_prompt
    mock_client.text_to_image.side_effect = [unsupported_err, dummy_image]

    with patch("services.image_generator.get_hf_token", return_value="hf_dummy_token"):
        with patch("services.image_generator.IMAGES_DIR", tmp_path):
            result = generate_image(
                prompt="Clean workspace with laptop",
                negative_prompt="clutter, blur",
                client=mock_client
            )

    assert result.is_success
    assert result.warning is not None
    assert "does not support negative prompts" in result.warning
    assert mock_client.text_to_image.call_count == 2
    # Second call should not have negative_prompt
    second_kwargs = mock_client.text_to_image.call_args_list[1][1]
    assert "negative_prompt" not in second_kwargs


def test_free_provider_fallback_on_402(dummy_image, tmp_path):
    """Test that when Hugging Face returns 402 (payment required), auto mode falls back to free provider."""
    mock_client = MagicMock()
    err_402 = _create_mock_hf_http_error(402, "402 Payment Required: Insufficient credits")
    mock_client.text_to_image.side_effect = err_402

    with patch("services.image_generator.get_hf_token", return_value="hf_dummy_token"):
        with patch("services.image_generator.generate_image_free_provider", return_value=dummy_image) as mock_free:
            with patch("services.image_generator.IMAGES_DIR", tmp_path):
                result = generate_image(
                    prompt="A futuristic flying car",
                    provider="auto",
                    client=mock_client
                )

    assert result.is_success
    assert result.model_used == "FLUX (Free Engine)"
    assert result.warning is not None
    assert "0 credits" in result.warning
    mock_free.assert_called_once()


def test_prompt_enhancer():
    """Test Groq-based prompt enhancer."""
    mock_choice = MagicMock()
    mock_choice.message.content = "A dramatic low-angle cinematic shot of a sprinter bursting from blocks."
    mock_response = MagicMock(choices=[mock_choice])

    with patch("services.image_generator.get_groq_api_key", return_value="gsk_dummy_key"):
        with patch("groq.Groq") as MockGroq:
            mock_instance = MockGroq.return_value
            mock_instance.chat.completions.create.return_value = mock_response

            enhanced = enhance_image_prompt("athlete sprinting", style="cinematic")
            assert "cinematic shot of a sprinter" in enhanced


def test_gemini_imagen3_generation(tmp_path):
    """Test successful image generation via Google Imagen 3."""
    import io
    test_img = Image.new("RGB", (512, 512), color="purple")
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    mock_generated_image = MagicMock()
    mock_generated_image.image.image_bytes = png_bytes
    mock_response = MagicMock(generated_images=[mock_generated_image])

    mock_client = MagicMock()
    mock_client.models.generate_images.return_value = mock_response

    with patch("services.image_generator.get_gemini_api_key", return_value="AIza_dummy_key"):
        with patch("services.image_generator.IMAGES_DIR", tmp_path):
            res = generate_image(
                prompt="A serene bamboo forest in misty morning light",
                style="photorealistic",
                aspect_ratio="1:1",
                provider="gemini",
                client=mock_client
            )

    assert res.is_success
    assert "Google Imagen 3" in (res.model_used or "")
    assert res.image_path is not None
    assert Path(res.image_path).exists()


def test_gemini_missing_key():
    """Test friendly error when Gemini API key is missing."""
    with patch("services.image_generator.get_gemini_api_key", side_effect=RuntimeError("GEMINI_API_KEY is not configured")):
        res = generate_image(prompt="A futuristic city", provider="gemini")
        assert not res.is_success
        assert "GEMINI_API_KEY is not configured" in (res.error or "")


def test_cloudflare_generation_binary_response(tmp_path):
    """Test successful image generation via Cloudflare Workers AI with binary image response."""
    import io
    test_img = Image.new("RGB", (512, 512), color="green")
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "image/png"}
    mock_resp.content = png_bytes

    with patch("services.image_generator.get_cloudflare_credentials", return_value=("cf_acc_123", "cf_tok_abc")):
        with patch("services.image_generator.httpx.post", return_value=mock_resp) as mock_post:
            with patch("services.image_generator.IMAGES_DIR", tmp_path):
                res = generate_image(
                    prompt="A futuristic neon skyscraper",
                    style="cinematic",
                    provider="cloudflare"
                )

    assert res.is_success
    assert "Cloudflare Workers AI" in (res.model_used or "")
    assert res.image_path is not None
    assert Path(res.image_path).exists()
    mock_post.assert_called_once()
    assert "cf_acc_123" in mock_post.call_args[0][0]


def test_cloudflare_generation_base64_response(tmp_path):
    """Test successful image generation via Cloudflare Workers AI with base64 JSON response."""
    import base64
    import io
    test_img = Image.new("RGB", (256, 256), color="orange")
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "result": {"image": b64_str},
        "success": True,
    }

    with patch("services.image_generator.get_cloudflare_credentials", return_value=("cf_acc_123", "cf_tok_abc")):
        with patch("services.image_generator.httpx.post", return_value=mock_resp):
            with patch("services.image_generator.IMAGES_DIR", tmp_path):
                res = generate_image(
                    prompt="A cozy coffee shop in autumn",
                    provider="cloudflare"
                )

    assert res.is_success
    assert "Cloudflare Workers AI" in (res.model_used or "")
    assert res.image_path is not None
    assert Path(res.image_path).exists()


def test_cloudflare_missing_credentials():
    """Test friendly error when Cloudflare credentials are not configured."""
    with patch(
        "services.image_generator.get_cloudflare_credentials",
        side_effect=RuntimeError("Cloudflare Workers AI credentials are not configured")
    ):
        res = generate_image(prompt="Space station orbiting Mars", provider="cloudflare")
        assert not res.is_success
        assert "Cloudflare Workers AI credentials are not configured" in (res.error or "")


def test_cloudflare_auth_error_401():
    """Test handling of Cloudflare 401 Unauthorized response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"

    with patch("services.image_generator.get_cloudflare_credentials", return_value=("cf_acc_123", "bad_token")):
        with patch("services.image_generator.httpx.post", return_value=mock_resp):
            res = generate_image(prompt="Cyberpunk street", provider="cloudflare")
            assert not res.is_success
            assert "401 Unauthorized" in (res.error or "")


def test_cloudflare_auto_priority_when_configured(dummy_image, tmp_path):
    """Test that Auto mode prioritizes Cloudflare Workers AI when credentials are configured."""
    with patch("services.image_generator.is_cloudflare_configured", return_value=True):
        with patch("services.image_generator.generate_image_cloudflare", return_value=dummy_image) as mock_cf:
            with patch("services.image_generator.IMAGES_DIR", tmp_path):
                res = generate_image(prompt="A mystical ancient temple", provider="auto")

    assert res.is_success
    assert "Cloudflare Workers AI" in (res.model_used or "")
    mock_cf.assert_called_once()

