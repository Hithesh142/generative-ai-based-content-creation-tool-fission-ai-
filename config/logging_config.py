"""
Fission AI - Centralized Logging Configuration
Provides thread-safe logging to data/logs/app.log with automatic secret redaction.
Prevents leaking API keys (Groq, HF, Gemini, Cloudflare) into log files.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
from typing import Optional

from config.settings import DATA_DIR

LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE_PATH = LOGS_DIR / "app.log"

# Regex patterns for sensitive tokens and keys
SECRET_PATTERNS = [
    (re.compile(r"gsk_[A-Za-z0-9_-]{20,}"), "gsk_***REDACTED***"),
    (re.compile(r"hf_[A-Za-z0-9_-]{20,}"), "hf_***REDACTED***"),
    (re.compile(r"AIza[A-Za-z0-9_-]{20,}"), "AIza_***REDACTED***"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE), "Bearer ***REDACTED***"),
    (re.compile(r"client/v4/accounts/[a-f0-9]{32}"), "client/v4/accounts/***REDACTED_ACCOUNT***"),
]


class SecretRedactingFormatter(logging.Formatter):
    """Logging formatter that redacts known secret patterns from all log records."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        redacted = original
        for pattern, replacement in SECRET_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted


_LOGGING_INITIALIZED = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Initialize root application logging configuration with rotating file handler."""
    global _LOGGING_INITIALIZED

    root_logger = logging.getLogger("fission_ai")
    root_logger.setLevel(level)

    if not _LOGGING_INITIALIZED:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        # File Handler (5 MB rotating file with 3 backups)
        file_handler = RotatingFileHandler(
            str(LOG_FILE_PATH),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_formatter = SecretRedactingFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        _LOGGING_INITIALIZED = True

    return root_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger under fission_ai namespace."""
    setup_logging()
    if name:
        return logging.getLogger(f"fission_ai.{name}")
    return logging.getLogger("fission_ai")
