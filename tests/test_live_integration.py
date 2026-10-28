"""
Fission AI - Live Integration Tests
Marked with @pytest.mark.live and skipped by default in pytest.ini.
Run explicitly with: pytest -m live
"""

import os
import pytest

from config.settings import is_groq_key_set
from services.content_generator import generate_content_ideas


@pytest.mark.live
def test_live_groq_generation():
    """Verify live Groq API connectivity and structured JSON generation."""
    if not is_groq_key_set():
        pytest.skip("GROQ_API_KEY not configured in environment.")

    result = generate_content_ideas(
        topic="Micro-habits for High Performance",
        platform="Twitter / X",
        number_of_ideas=1,
    )
    assert "ideas" in result
    assert len(result["ideas"]) >= 1
    assert "hook" in result["ideas"][0]
