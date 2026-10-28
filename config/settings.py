"""
Fission AI - Configuration and Environment Settings
Handles loading environment variables, exposing paths, and validating keys.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Base directory: root of the fission_ai repository
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Directory and Database Paths
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "fission.db"))).resolve()

# Ensure essential directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Configuration values
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY", "").strip()
    or os.getenv("GOOGLE_API_KEY", "").strip()
)
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
CLOUDFLARE_IMAGE_MODEL = os.getenv(
    "CLOUDFLARE_IMAGE_MODEL",
    "@cf/black-forest-labs/flux-1-schnell"
).strip()

# Image Generation Models
DEFAULT_IMAGE_MODEL = os.getenv(
    "DEFAULT_IMAGE_MODEL",
    "black-forest-labs/FLUX.1-schnell"
).strip()

FALLBACK_IMAGE_MODELS = [
    model.strip()
    for model in os.getenv(
        "FALLBACK_IMAGE_MODELS",
        "black-forest-labs/FLUX.1-dev,stabilityai/stable-diffusion-xl-base-1.0"
    ).split(",")
    if model.strip()
]


def is_groq_key_set() -> bool:
    """Check if GROQ_API_KEY is configured without exposing the key."""
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def is_hf_token_set() -> bool:
    """Check if HF_TOKEN is configured without exposing the token."""
    return bool(os.getenv("HF_TOKEN", "").strip())


def is_gemini_key_set() -> bool:
    """Check if GEMINI_API_KEY is configured without exposing the key."""
    return bool(
        os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GOOGLE_API_KEY", "").strip()
    )


def is_cloudflare_configured() -> bool:
    """Check if Cloudflare account ID and API token are set."""
    return bool(
        os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        and os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    )


def get_groq_api_key() -> str:
    """
    Returns the GROQ_API_KEY.
    If missing, raises a user-friendly RuntimeError with step-by-step instructions.
    Never prints or leaks the key value.
    """
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured.\n\n"
            "Please follow these steps to set it up:\n"
            "1. Copy .env.example to .env in the project root.\n"
            "2. Open .env and set: GROQ_API_KEY=your_actual_key\n"
            "3. Obtain a free API key at https://console.groq.com/keys\n"
            "4. Restart the application."
        )
    return key


def get_hf_token() -> str:
    """
    Returns the HF_TOKEN.
    If missing, raises a user-friendly RuntimeError with instructions.
    """
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "HF_TOKEN is not configured.\n\n"
            "Please follow these steps to set it up:\n"
            "1. Open .env in the project root.\n"
            "2. Add your Hugging Face token: HF_TOKEN=your_token_here\n"
            "3. Obtain a token at https://huggingface.co/settings/tokens\n"
            "   (Ensure 'Make calls to Inference Providers' permission is enabled)."
        )
    return token


def get_gemini_api_key() -> str:
    """
    Returns the GEMINI_API_KEY.
    If missing, raises a user-friendly RuntimeError with instructions.
    Never prints or leaks the key value.
    """
    key = (
        os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GOOGLE_API_KEY", "").strip()
    )
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured.\n\n"
            "Please follow these steps to set it up:\n"
            "1. Open .env in the project root.\n"
            "2. Add your Gemini API key: GEMINI_API_KEY=AIza...\n"
            "3. Obtain a free API key at https://aistudio.google.com/app/apikey\n"
            "4. Restart the application."
        )
    return key


def get_cloudflare_credentials() -> tuple[str, str]:
    """
    Returns (account_id, api_token) for Cloudflare Workers AI.
    Raises friendly instructions if not configured.
    Never prints or leaks secrets.
    """
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account_id or not token:
        raise RuntimeError(
            "Cloudflare Workers AI credentials are not configured.\n\n"
            "Please follow these steps to set it up:\n"
            "1. Open .env in your project root.\n"
            "2. Add:\n"
            "   CLOUDFLARE_ACCOUNT_ID=your_32_char_account_id\n"
            "   CLOUDFLARE_API_TOKEN=your_workers_ai_token\n"
            "3. Find your Account ID at https://dash.cloudflare.com/ (right sidebar or URL)\n"
            "4. Create an API token at https://dash.cloudflare.com/profile/api-tokens with Workers AI permission.\n"
            "5. Restart the application."
        )
    return account_id, token


def check_directories_writable() -> dict[str, bool]:
    """
    Check if the required data directories are writable.
    Returns a dictionary mapping directory name to writability status.
    """
    status = {}
    for name, directory in [("data", DATA_DIR), ("images", IMAGES_DIR)]:
        try:
            test_file = directory / ".writable_test"
            test_file.touch(exist_ok=True)
            test_file.unlink(missing_ok=True)
            status[name] = True
        except Exception:
            status[name] = False
    return status
