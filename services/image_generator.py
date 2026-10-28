"""
Fission AI - Image Generation Service
Uses Hugging Face InferenceClient with HF_TOKEN from config.settings.
Includes prompt validation, style presets, aspect ratio resolution mapping,
exponential backoff retry on transient errors, and unique image storage in data/images/.
Provides an automatic Free FLUX Engine fallback for accounts with zero HF credits.
Also provides an AI Prompt Enhancer powered by Groq.
"""

import datetime
import io
import os
import re
import sys
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import httpx
from huggingface_hub import InferenceClient
import huggingface_hub.errors as hf_errors
from PIL import Image

from config.settings import (
    CLOUDFLARE_IMAGE_MODEL,
    DEFAULT_IMAGE_MODEL,
    FALLBACK_IMAGE_MODELS,
    GROQ_MODEL,
    IMAGES_DIR,
    get_cloudflare_credentials,
    get_gemini_api_key,
    get_groq_api_key,
    get_hf_token,
    is_cloudflare_configured,
    is_gemini_key_set,
    is_hf_token_set,
)


# ============================================================
# CONSTANTS & CONFIGURATION
# ============================================================

MAX_PROMPT_LENGTH = 1500

ASPECT_RATIO_MAP: Dict[str, Tuple[int, int]] = {
    "1:1": (1024, 1024),
    "4:5": (896, 1120),
    "9:16": (576, 1024),
    "16:9": (1024, 576),
}

STYLE_PRESETS: Dict[str, str] = {
    "photorealistic": (
        "photorealistic, hyperrealistic 8k, extremely detailed, natural studio lighting, "
        "professional photography, high resolution, sharp focus"
    ),
    "cinematic": (
        "cinematic lighting, dramatic atmosphere, 35mm lens, depth of field, 8k resolution, "
        "movie still, rich contrast, film grain"
    ),
    "illustration": (
        "digital illustration, expressive vibrant art style, clean vector lines, "
        "creative composition, detailed graphic artwork"
    ),
    "3D": (
        "3D render, Pixar style, ray tracing, octane render, soft volumetric lighting, "
        "vibrant textures, high detail, 4k"
    ),
    "minimalist": (
        "minimalist aesthetic, clean composition, uncluttered background, simple forms, "
        "elegant typography, muted refined colors"
    ),
    "editorial": (
        "editorial fashion photography, high aesthetic, sophisticated studio lighting, "
        "Vogue editorial style, sharp detail, contemporary elegance"
    ),
    "none": "",
}


@dataclass
class ImageGenerationResult:
    """Typed result object for image generation."""
    image: Optional[Image.Image] = None
    image_path: Optional[str] = None
    prompt: str = ""
    styled_prompt: str = ""
    model_used: Optional[str] = None
    style: str = "photorealistic"
    aspect_ratio: str = "1:1"
    width: int = 1024
    height: int = 1024
    error: Optional[str] = None
    warning: Optional[str] = None
    is_success: bool = False


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _redact_secrets(text: str) -> str:
    """Redact any accidental tokens or keys from error messages."""
    text = re.sub(r"hf_[A-Za-z0-9]{20,}", "hf_***REDACTED***", text)
    text = re.sub(r"gsk_[A-Za-z0-9]{20,}", "gsk_***REDACTED***", text)
    return text


def validate_prompt(prompt: str) -> Tuple[bool, Optional[str]]:
    """Validate prompt presence and length."""
    if not prompt or not prompt.strip():
        return False, "Prompt cannot be empty. Please enter an image prompt."
    if len(prompt.strip()) > MAX_PROMPT_LENGTH:
        return False, (
            f"Prompt exceeds the limit of {MAX_PROMPT_LENGTH} characters "
            f"(currently {len(prompt.strip())} characters)."
        )
    return True, None


def apply_style_preset(prompt: str, style: str) -> str:
    """Combine base prompt with chosen style preset."""
    style_key = style.lower().strip()
    modifier = STYLE_PRESETS.get(style_key, "")
    if modifier:
        return f"{prompt.strip()}, {modifier}"
    return prompt.strip()


def save_image_to_storage(image: Image.Image) -> str:
    """
    Save generated PIL Image to data/images/ with a safe, unique filename (timestamp + uuid).
    Returns the absolute path as a string.
    """
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    filename = f"fission_{timestamp}_{unique_id}.png"
    filepath = IMAGES_DIR / filename
    image.save(filepath, format="PNG")
    return str(filepath)


def _parse_hf_error(err: Exception) -> Tuple[Optional[int], str, bool]:
    """
    Classify Hugging Face errors and determine if they are transient.
    Returns: (status_code, clean_message, is_transient)
    """
    status_code = getattr(getattr(err, "response", None), "status_code", None)
    err_str = _redact_secrets(str(err))

    # 401 Unauthorized
    if status_code == 401 or "unauthorized" in err_str.lower():
        return 401, (
            "Authentication failed (401 Unauthorized).\n"
            "Please check that your HF_TOKEN in .env is valid."
        ), False

    # 403 Forbidden
    if status_code == 403:
        if "inference providers" in err_str.lower() or "sufficient permissions" in err_str.lower():
            return 403, (
                "Hugging Face permission error (403 Forbidden): Your HF_TOKEN lacks "
                "'Make calls to Inference Providers' permission.\n\n"
                "To fix:\n"
                "1. Go to https://huggingface.co/settings/tokens\n"
                "2. Create a new token or edit your existing token\n"
                "3. Ensure the 'Make calls to Inference Providers' permission is checked\n"
                "4. Update HF_TOKEN in your .env file and restart."
            ), False
        elif "gated" in err_str.lower():
            return 403, (
                "This model is gated (403 Forbidden). You must request and be granted "
                "access to this repository on Hugging Face before using it."
            ), False
        else:
            return 403, (
                f"Access forbidden (403 Forbidden). Token lacks required permissions.\n"
                f"Details: {err_str}"
            ), False

    # 402 Payment Required / Credits
    if status_code == 402 or "payment" in err_str.lower() or "credits" in err_str.lower():
        return 402, (
            "Insufficient credits (402 Payment Required).\n\n"
            "Hugging Face routes modern image generation models (such as FLUX.1 and SDXL) through "
            "Inference Providers (nscale, fal-ai, wavespeed) which require paid inference credits.\n\n"
            "How to resolve:\n"
            "1. Go to https://huggingface.co/settings/billing\n"
            "2. Add pre-paid Inference Credits (e.g. $5 gives ~1,500 FLUX generations at ~$0.003/image)\n"
            "3. Once added, click 'Retry' or 'Generate Image' to produce your image."
        ), False

    # 404 / StopIteration (No provider)
    if status_code == 404 or isinstance(err, StopIteration) or "no provider" in err_str.lower():
        return 404, "No inference provider found for this model on Hugging Face (404 / No Provider).", False

    # Transient: 429 Rate Limit
    if status_code == 429:
        return 429, "Hugging Face rate limit exceeded (429 Too Many Requests).", True

    # Transient: Server Errors (500, 502, 503, 504)
    if status_code in (500, 502, 503, 504) or isinstance(err, hf_errors.OverloadedError):
        return status_code or 503, (
            f"Hugging Face inference provider temporary error ({status_code or 503}). "
            "Server may be busy or reloading."
        ), True

    # Transient: Timeouts
    if isinstance(err, (hf_errors.InferenceTimeoutError, httpx.TimeoutException)) or "timeout" in err_str.lower():
        return None, "Request timed out while waiting for image generation. The provider might be busy.", True

    return status_code, f"Image generation failed: {err_str}", False


# ============================================================
# FREE PROVIDER ENGINE (POLLINATIONS FLUX)
# ============================================================

def generate_image_free_provider(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    timeout: float = 60.0,
) -> Image.Image:
    """
    Generate an image using the free Pollinations FLUX engine.
    Requires no paid credits or API tokens.
    """
    encoded_prompt = urllib.parse.quote(prompt.strip())
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
    params: Dict[str, Any] = {
        "width": width,
        "height": height,
        "model": "flux",
        "nologo": "true",
    }
    if negative_prompt and negative_prompt.strip():
        params["negative_prompt"] = negative_prompt.strip()
    if seed is not None:
        params["seed"] = seed

    response = httpx.get(url, params=params, timeout=timeout, follow_redirects=True)
    if response.status_code != 200:
        resp_text = response.text
        if response.status_code == 503 or "limit right now" in resp_text:
            raise RuntimeError(
                "Free engine server is temporarily at capacity (503 Service Unavailable). "
                "Please wait ~30 seconds and click 'Retry', or add $5 credits on Hugging Face for dedicated compute."
            )
        if response.status_code == 402 or "every 45 seconds" in resp_text:
            raise RuntimeError(
                "Free engine rate limit reached (1 image every 45 seconds on free tier). "
                "Please wait ~30 seconds and click 'Retry'."
            )
        raise RuntimeError(
            f"Free engine error ({response.status_code}): {_redact_secrets(resp_text[:120])}"
        )

    image = Image.open(io.BytesIO(response.content))
    return image


# ============================================================
# GOOGLE IMAGEN 3 GENERATOR (GEMINI API)
# ============================================================

def generate_image_gemini(
    prompt: str,
    aspect_ratio: str = "1:1",
    negative_prompt: Optional[str] = None,
    client: Optional[Any] = None,
) -> Image.Image:
    """
    Generate an image using Google's Imagen 3 model via the google-genai SDK.
    Requires GEMINI_API_KEY.
    """
    from google import genai
    from google.genai import types

    if client is None:
        api_key = get_gemini_api_key()
        client = genai.Client(api_key=api_key)

    # Imagen 3 supported aspect ratios: "1:1", "3:4", "4:3", "9:16", "16:9"
    ratio_map = {
        "1:1": "1:1",
        "4:5": "3:4",  # Closest standard ratio for portrait
        "9:16": "9:16",
        "16:9": "16:9",
    }
    target_ratio = ratio_map.get(aspect_ratio, "1:1")

    config_kwargs: Dict[str, Any] = {
        "number_of_images": 1,
        "aspect_ratio": target_ratio,
        "output_mime_type": "image/png",
    }
    if negative_prompt and negative_prompt.strip():
        config_kwargs["negative_prompt"] = negative_prompt.strip()

    config = types.GenerateImagesConfig(**config_kwargs)

    result = client.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt=prompt,
        config=config,
    )

    if not result or not result.generated_images:
        raise RuntimeError("Google Imagen 3 did not return any images.")

    image_bytes = result.generated_images[0].image.image_bytes
    image = Image.open(io.BytesIO(image_bytes))
    return image


# ============================================================
# CLOUDFLARE WORKERS AI GENERATOR
# ============================================================

def generate_image_cloudflare(
    prompt: str,
    model: Optional[str] = None,
    num_steps: int = 4,
    account_id: Optional[str] = None,
    api_token: Optional[str] = None,
    client: Optional[Any] = None,
    timeout: float = 60.0,
) -> Image.Image:
    """
    Generate an image using Cloudflare Workers AI.
    Runs on Cloudflare's serverless GPU network (10,000 free Neurons/day).
    Model: @cf/black-forest-labs/flux-1-schnell or @cf/stabilityai/stable-diffusion-xl-base-1.0
    """
    import base64

    # Allow passing mock client for testing
    if client is not None:
        response = client.post(prompt=prompt, model=model)
        if isinstance(response, Image.Image):
            return response
        if isinstance(response, bytes):
            return Image.open(io.BytesIO(response))

    if not account_id or not api_token:
        account_id, api_token = get_cloudflare_credentials()

    target_model = model or CLOUDFLARE_IMAGE_MODEL
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{target_model}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "prompt": prompt.strip(),
        "steps": num_steps,
    }

    response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    if response.status_code != 200:
        err_text = response.text
        if response.status_code == 401:
            raise RuntimeError(
                "Cloudflare authentication failed (401 Unauthorized).\n"
                "Please verify your CLOUDFLARE_API_TOKEN in .env has 'Workers AI' permission."
            )
        elif response.status_code == 404:
            raise RuntimeError(
                f"Cloudflare returned 404 Not Found. Please check your CLOUDFLARE_ACCOUNT_ID "
                f"and verify model '{target_model}' is supported."
            )
        elif response.status_code == 429:
            raise RuntimeError(
                "Cloudflare rate limit reached (429 Too Many Requests). Please wait a moment."
            )
        raise RuntimeError(
            f"Cloudflare Workers AI error ({response.status_code}): {_redact_secrets(err_text[:150])}"
        )

    # Cloudflare can return binary image or JSON with base64 image
    content_type = response.headers.get("content-type", "")
    if "image/" in content_type:
        image = Image.open(io.BytesIO(response.content))
        return image

    try:
        data = response.json()
        if "result" in data and "image" in data["result"]:
            b64_str = data["result"]["image"]
            image = Image.open(io.BytesIO(base64.b64decode(b64_str)))
            return image
        raise RuntimeError(f"Unexpected Cloudflare response structure: {list(data.keys())}")
    except Exception as parse_err:
        raise RuntimeError(f"Failed to parse Cloudflare image output: {parse_err}")


# ============================================================
# MAIN GENERATE FUNCTION
# ============================================================

def generate_image(
    prompt: str,
    style: str = "photorealistic",
    aspect_ratio: str = "1:1",
    negative_prompt: Optional[str] = None,
    model: Optional[str] = None,
    provider: str = "auto",
    client: Optional[InferenceClient] = None,
) -> ImageGenerationResult:
    """
    Generate an image using Hugging Face InferenceClient with seamless Free FLUX Engine fallback.

    Args:
        prompt: Raw image prompt.
        style: Style preset key (photorealistic, cinematic, illustration, 3D, minimalist, editorial).
        aspect_ratio: Aspect ratio key (1:1, 4:5, 9:16, 16:9).
        negative_prompt: Optional negative prompt.
        model: Custom model name (default: black-forest-labs/FLUX.1-schnell).
        provider: "auto" (HF with free fallback), "free" (Free FLUX engine), or "hf" (HF only).
        client: Optional pre-configured InferenceClient (useful for mocking).
    """
    # 1. Validate prompt
    is_valid, validation_err = validate_prompt(prompt)
    if not is_valid:
        return ImageGenerationResult(
            prompt=prompt,
            style=style,
            aspect_ratio=aspect_ratio,
            error=validation_err,
            is_success=False,
        )

    # 2. Determine dimensions
    width, height = ASPECT_RATIO_MAP.get(aspect_ratio, (1024, 1024))

    # 3. Apply style preset
    styled_prompt = apply_style_preset(prompt, style)
    active_negative = negative_prompt.strip() if negative_prompt and negative_prompt.strip() else None

    # 4. Cloudflare Workers AI Provider mode
    if provider.lower() in ("cloudflare", "cf"):
        try:
            cf_img = generate_image_cloudflare(
                prompt=styled_prompt,
                model=model,
                client=client if (client and hasattr(client, "post")) else None
            )
            saved_path = save_image_to_storage(cf_img)
            return ImageGenerationResult(
                image=cf_img,
                image_path=saved_path,
                prompt=prompt,
                styled_prompt=styled_prompt,
                model_used=f"Cloudflare Workers AI ({model or CLOUDFLARE_IMAGE_MODEL})",
                style=style,
                aspect_ratio=aspect_ratio,
                width=getattr(cf_img, "width", width),
                height=getattr(cf_img, "height", height),
                is_success=True,
            )
        except Exception as cf_err:
            return ImageGenerationResult(
                prompt=prompt,
                styled_prompt=styled_prompt,
                model_used="Cloudflare Workers AI",
                style=style,
                aspect_ratio=aspect_ratio,
                width=width,
                height=height,
                error=f"Cloudflare Workers AI error: {str(cf_err)}",
                is_success=False,
            )

    # In Auto mode, if Cloudflare is configured (and no specific HF client was passed), prioritize Cloudflare (10,000 free Neurons/day)
    if provider.lower() == "auto" and is_cloudflare_configured() and not (client and hasattr(client, "text_to_image")):
        try:
            cf_img = generate_image_cloudflare(
                prompt=styled_prompt,
                model=model,
                client=client if (client and hasattr(client, "post")) else None
            )
            saved_path = save_image_to_storage(cf_img)
            return ImageGenerationResult(
                image=cf_img,
                image_path=saved_path,
                prompt=prompt,
                styled_prompt=styled_prompt,
                model_used=f"Cloudflare Workers AI ({model or CLOUDFLARE_IMAGE_MODEL})",
                style=style,
                aspect_ratio=aspect_ratio,
                width=getattr(cf_img, "width", width),
                height=getattr(cf_img, "height", height),
                is_success=True,
            )
        except Exception:
            # Fall through to HF / Free Engine if Cloudflare fails
            pass

    # 5. Google Imagen 3 Provider mode
    if provider.lower() in ("gemini", "google", "imagen"):
        try:
            gemini_img = generate_image_gemini(
                prompt=styled_prompt,
                aspect_ratio=aspect_ratio,
                negative_prompt=active_negative,
                client=client if (client and hasattr(client, "models")) else None
            )
            saved_path = save_image_to_storage(gemini_img)
            return ImageGenerationResult(
                image=gemini_img,
                image_path=saved_path,
                prompt=prompt,
                styled_prompt=styled_prompt,
                model_used="Google Imagen 3 (imagen-3.0-generate-002)",
                style=style,
                aspect_ratio=aspect_ratio,
                width=width,
                height=height,
                is_success=True,
            )
        except Exception as gemini_err:
            err_str = str(gemini_err)
            if "Enterprise Agent Platform mode" in err_str or "Developer API mode" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                err_clean = (
                    "Google restricts Imagen 3 generation to Google Cloud Vertex AI accounts. "
                    "Standard Google AI Studio API keys do not include Imagen 3 generation quota.\n\n"
                    "👉 Recommended Action: In the sidebar under 'Image Engine', switch to "
                    "'Free Engine (FLUX)' to generate your images with zero credits required."
                )
            else:
                err_clean = f"Google Imagen 3 error: {_redact_secrets(err_str)}"

            return ImageGenerationResult(
                prompt=prompt,
                styled_prompt=styled_prompt,
                model_used="Google Imagen 3",
                style=style,
                aspect_ratio=aspect_ratio,
                width=width,
                height=height,
                error=err_clean,
                is_success=False,
            )

    # 5. Direct Free Provider mode
    if provider.lower() == "free":
        try:
            free_img = generate_image_free_provider(
                prompt=styled_prompt,
                width=width,
                height=height,
                negative_prompt=active_negative
            )
            saved_path = save_image_to_storage(free_img)
            return ImageGenerationResult(
                image=free_img,
                image_path=saved_path,
                prompt=prompt,
                styled_prompt=styled_prompt,
                model_used="FLUX (Free Engine)",
                style=style,
                aspect_ratio=aspect_ratio,
                width=width,
                height=height,
                is_success=True,
            )
        except Exception as free_err:
            return ImageGenerationResult(
                prompt=prompt,
                styled_prompt=styled_prompt,
                model_used="FLUX (Free Engine)",
                style=style,
                aspect_ratio=aspect_ratio,
                error=f"Free engine error: {str(free_err)}",
                is_success=False,
            )

    # 5. Check HF token
    try:
        token = get_hf_token()
    except RuntimeError as err:
        if provider.lower() == "auto":
            # Seamless fallback to free engine if HF token is missing
            try:
                free_img = generate_image_free_provider(
                    prompt=styled_prompt,
                    width=width,
                    height=height,
                    negative_prompt=active_negative
                )
                saved_path = save_image_to_storage(free_img)
                return ImageGenerationResult(
                    image=free_img,
                    image_path=saved_path,
                    prompt=prompt,
                    styled_prompt=styled_prompt,
                    model_used="FLUX (Free Engine)",
                    style=style,
                    aspect_ratio=aspect_ratio,
                    width=width,
                    height=height,
                    warning="HF_TOKEN was not configured. Generated via Free FLUX Engine.",
                    is_success=True,
                )
            except Exception as free_err:
                return ImageGenerationResult(
                    prompt=prompt,
                    style=style,
                    aspect_ratio=aspect_ratio,
                    error=f"Both HF and Free engine failed: {free_err}",
                    is_success=False,
                )

        return ImageGenerationResult(
            prompt=prompt,
            style=style,
            aspect_ratio=aspect_ratio,
            error=str(err),
            is_success=False,
        )

    # 6. Initialize client if not provided
    if client is None:
        client = InferenceClient(token=token, timeout=90.0)

    target_model = model or DEFAULT_IMAGE_MODEL

    # 7. Execution loop with transient retry and negative_prompt fallback
    max_retries = 2
    warning_msg = None
    hf_error_details = None

    for attempt in range(max_retries + 1):
        try:
            kwargs: Dict[str, Any] = {
                "model": target_model,
                "width": width,
                "height": height,
            }
            if active_negative:
                kwargs["negative_prompt"] = active_negative

            generated_image: Image.Image = client.text_to_image(
                styled_prompt,
                **kwargs
            )

            # Save generated image to storage
            saved_path = save_image_to_storage(generated_image)

            return ImageGenerationResult(
                image=generated_image,
                image_path=saved_path,
                prompt=prompt,
                styled_prompt=styled_prompt,
                model_used=target_model,
                style=style,
                aspect_ratio=aspect_ratio,
                width=width,
                height=height,
                warning=warning_msg,
                is_success=True,
            )

        except Exception as exc:
            exc_str = str(exc).lower()
            status_code = getattr(getattr(exc, "response", None), "status_code", None)

            # Handle unsupported negative prompt
            if active_negative and (status_code == 422 or "negative_prompt" in exc_str or "unsupported" in exc_str):
                active_negative = None
                warning_msg = f"Model '{target_model}' does not support negative prompts. Generated without negative prompt."
                continue

            status_code, err_msg, is_transient = _parse_hf_error(exc)
            hf_error_details = err_msg

            # Retry transient errors
            if is_transient and attempt < max_retries:
                backoff_time = 1.5 * (2 ** attempt)
                time.sleep(backoff_time)
                continue

            # If provider is "auto" and error is 402 (no credits), fall back to Free FLUX engine
            if provider.lower() == "auto" and (status_code == 402 or "credit" in exc_str or "payment" in exc_str):
                try:
                    free_img = generate_image_free_provider(
                        prompt=styled_prompt,
                        width=width,
                        height=height,
                        negative_prompt=active_negative
                    )
                    saved_path = save_image_to_storage(free_img)
                    return ImageGenerationResult(
                        image=free_img,
                        image_path=saved_path,
                        prompt=prompt,
                        styled_prompt=styled_prompt,
                        model_used="FLUX (Free Engine)",
                        style=style,
                        aspect_ratio=aspect_ratio,
                        width=width,
                        height=height,
                        warning=(
                            "Hugging Face account has 0 credits. Successfully generated using the Free FLUX Engine!\n"
                            "(To use official HF inference, add pre-paid credits at https://huggingface.co/settings/billing)."
                        ),
                        is_success=True,
                    )
                except Exception as fb_err:
                    return ImageGenerationResult(
                        prompt=prompt,
                        styled_prompt=styled_prompt,
                        model_used=target_model,
                        style=style,
                        aspect_ratio=aspect_ratio,
                        error=(
                            f"Image generation could not be completed:\n\n"
                            f"1. **Hugging Face Inference:** Requires pre-paid credits (402 Payment Required). "
                            f"Add credits at https://huggingface.co/settings/billing.\n"
                            f"2. **Free Engine Fallback:** {fb_err}\n\n"
                            f"👉 **Next step:** If using the free engine, wait ~30-45 seconds and click **'🔁 Retry'**."
                        ),
                        is_success=False,
                    )

            # Otherwise return HF error
            return ImageGenerationResult(
                prompt=prompt,
                styled_prompt=styled_prompt,
                model_used=target_model,
                style=style,
                aspect_ratio=aspect_ratio,
                width=width,
                height=height,
                error=err_msg,
                warning=warning_msg,
                is_success=False,
            )

    return ImageGenerationResult(
        prompt=prompt,
        styled_prompt=styled_prompt,
        model_used=target_model,
        style=style,
        aspect_ratio=aspect_ratio,
        error=hf_error_details or "Image generation failed after retries.",
        is_success=False,
    )


# ============================================================
# PROMPT ENHANCER (GROQ)
# ============================================================

def enhance_image_prompt(
    prompt: str,
    style: str = "photorealistic",
    brand_profile: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Expands an image concept using Groq into a detailed prompt with
    lighting, composition, camera details, textures, and color palette.
    Injects brand visual identity (colors/mood) if configured.
    """
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    api_key = get_groq_api_key()
    from groq import Groq
    client = Groq(api_key=api_key)

    color_cue = ""
    if brand_profile and brand_profile.get("brand_colors"):
        color_cue = f" Align the mood and color grading with brand palette: {brand_profile['brand_colors']}."

    system_instruction = (
        "You are an expert prompt engineer for AI image models (FLUX, Midjourney). "
        "Expand the given image concept into a vivid, descriptive prompt detailing: "
        "focal subjects, lighting (e.g. volumetric, rim lighting), "
        "composition/framing (e.g. cinematic wide shot, shallow depth of field), "
        "textures, and color palette."
        f"{color_cue} "
        "Keep the output under 75 words. "
        "Return ONLY the prompt text. Do NOT include greetings, intro phrases, quotes, or markdown."
    )

    user_content = f"Concept: {prompt.strip()}\nTarget Style: {style}"

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ],
        temperature=0.7,
        max_tokens=1500
    )

    enhanced = response.choices[0].message.content.strip()
    if enhanced.startswith('"') and enhanced.endswith('"'):
        enhanced = enhanced[1:-1].strip()

    return enhanced
