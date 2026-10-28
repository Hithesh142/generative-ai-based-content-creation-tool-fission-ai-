"""
Test suite for Phase 1 tasks:
- config/settings.py
- services/content_generator.py (schema validation, fallbacks, retry logic)
- environment variables and friendly missing key behavior
"""

import os
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.settings import (
    BASE_DIR,
    DATA_DIR,
    IMAGES_DIR,
    DB_PATH,
    GROQ_MODEL,
    is_groq_key_set,
    is_hf_token_set,
    check_directories_writable,
    get_groq_api_key,
    get_hf_token,
)
from services.content_generator import (
    ContentIdea,
    ContentStrategyResponse,
    _extract_json,
    _apply_fallbacks,
    generate_content_ideas,
)


def test_settings_paths():
    assert DATA_DIR.exists(), "DATA_DIR does not exist"
    assert IMAGES_DIR.exists(), "IMAGES_DIR does not exist"
    assert DB_PATH.name in ("fission.db", "fission_ai.db"), f"Unexpected DB_PATH: {DB_PATH}"
    print("PASS: Settings paths verified.")


def test_settings_writable():
    writable_map = check_directories_writable()
    assert writable_map.get("data") is True, "data directory is not writable"
    assert writable_map.get("images") is True, "images directory is not writable"
    print("PASS: Data directories writable verified.")


def test_missing_groq_key_friendly_error():
    with patch.dict(os.environ, {}, clear=True):
        assert not is_groq_key_set(), "GROQ key should not be detected when unset"
        try:
            get_groq_api_key()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            err_text = str(e)
            assert "GROQ_API_KEY is not configured" in err_text
            assert "https://console.groq.com/keys" in err_text
            print("PASS: Friendly missing key error verified.")


def test_extract_json():
    # Code fence with json
    sample_1 = '```json\n{"topic": "Tech", "ideas": []}\n```'
    assert _extract_json(sample_1) == '{"topic": "Tech", "ideas": []}'

    # Code fence without language tag
    sample_2 = '```\n{"topic": "Tech", "ideas": []}\n```'
    assert _extract_json(sample_2) == '{"topic": "Tech", "ideas": []}'

    # Conversational text surrounding JSON
    sample_3 = 'Here is the response:\n{"topic": "Tech", "ideas": []}\nHope this helps!'
    assert _extract_json(sample_3) == '{"topic": "Tech", "ideas": []}'
    print("PASS: JSON extraction verified.")


def test_pydantic_schema_and_fallbacks():
    sample_idea = {
        "title": "5 Tips for Muscle Growth",
        "content_type": "Reel",
        "hook": "Stop wasting hours in the gym!",
        "caption": "Here are 5 science-backed tips for hypertrophy.",
        "call_to_action": "Follow for daily fitness tips!",
        "hashtags": "fitness, bodybuilding, hypertrophy",
        "visual_concept": "Fast cuts of proper lifting form",
        "image_prompt": "Cinematic shot of weightlifter in gym with chalk dust and dramatic lighting"
    }

    raw_payload = {
        "topic": "Bodybuilding",
        "ideas": [sample_idea]
    }

    # Verify fallbacks fill missing target_audience and duration_estimate
    augmented = _apply_fallbacks(
        raw_payload,
        fallback_audience="Fitness Enthusiasts",
        fallback_format="Reel",
        keywords="hypertrophy, lifting",
        campaign_objective="Audience Engagement"
    )

    idea = augmented["ideas"][0]
    assert idea["target_audience"] == "Fitness Enthusiasts", f"Unexpected audience: {idea['target_audience']}"
    assert "30-60 seconds" in idea["duration_estimate"], f"Unexpected duration: {idea['duration_estimate']}"

    # Verify Pydantic validation
    model = ContentStrategyResponse.model_validate(augmented)
    assert len(model.ideas) == 1
    assert model.ideas[0].hashtags == ["#fitness", "#bodybuilding", "#hypertrophy"]
    assert model.campaign_objective == "Audience Engagement"
    assert model.keywords == ["hypertrophy", "lifting"]
    print("PASS: Pydantic schema and fallbacks verified.")


def test_retry_on_malformed_json():
    # Mock Groq client to return bad JSON on attempt 1, valid JSON on attempt 2
    mock_bad_choice = MagicMock()
    mock_bad_choice.message.content = "Not valid JSON at all"
    mock_bad_response = MagicMock(choices=[mock_bad_choice])

    valid_json_text = json.dumps({
        "topic": "Bodybuilding",
        "ideas": [
            {
                "title": "Test Title",
                "content_type": "Reel",
                "hook": "Hook",
                "caption": "Caption",
                "call_to_action": "CTA",
                "hashtags": ["#gym"],
                "visual_concept": "Visual",
                "image_prompt": "Prompt",
                "target_audience": "Beginners",
                "duration_estimate": "30s"
            }
        ]
    })
    mock_good_choice = MagicMock()
    mock_good_choice.message.content = valid_json_text
    mock_good_response = MagicMock(choices=[mock_good_choice])

    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_dummy_test_key"}):
        with patch("services.content_generator.Groq") as MockGroq:
            mock_client = MockGroq.return_value
            mock_client.chat.completions.create.side_effect = [
                mock_bad_response,
                mock_good_response
            ]

            result = generate_content_ideas(
                topic="Bodybuilding",
                audience="Beginners",
                keywords="gym",
                campaign_objective="Engagement"
            )

            assert mock_client.chat.completions.create.call_count == 2, "Expected exactly 2 attempts"
            assert result["topic"] == "Bodybuilding"
            assert len(result["ideas"]) == 1
            print("PASS: Retry on malformed JSON verified.")


if __name__ == "__main__":
    test_settings_paths()
    test_settings_writable()
    test_missing_groq_key_friendly_error()
    test_extract_json()
    test_pydantic_schema_and_fallbacks()
    test_retry_on_malformed_json()
    print("\nSUCCESS: ALL UNIT TESTS PASSED!")
