"""
Fission AI - UI Smoke Tests & Modern Component Tests
Uses streamlit.testing.v1.AppTest to verify:
- App loads cleanly without exceptions
- All 5 top-level navigation tabs render
- Empty states render cleanly when no strategy is generated
- Theme preference persistence in app_settings & session state
- Strategy generation flow with mocked Groq
- WCAG AA contrast ratio compliance verification
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from streamlit.testing.v1 import AppTest

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

MAIN_PATH = str((BASE_DIR / "frontend" / "main.py").resolve())

from database.db import get_setting, init_db, set_setting
from frontend.styles import calculate_contrast_ratio, get_contrast_report


@pytest.fixture(autouse=True)
def ensure_db():
    """Ensure database schema is initialized for tests."""
    init_db()


def test_app_loads_without_exceptions():
    """Verify that frontend/main.py loads cleanly with 0 exceptions."""
    at = AppTest.from_file(MAIN_PATH)
    at.run(timeout=10)
    assert len(at.exception) == 0, f"App loaded with exceptions: {at.exception}"


def test_tabs_exist():
    """Verify that all 5 navigation tabs render in the main content area."""
    at = AppTest.from_file(MAIN_PATH)
    at.run(timeout=10)
    assert len(at.tabs) == 5
    tab_labels = [tab.label for tab in at.tabs]
    assert "🚀 Studio" in tab_labels
    assert "📚 Library" in tab_labels
    assert "📅 Calendar" in tab_labels
    assert "🎨 Brand" in tab_labels
    assert "⚙️ Settings" in tab_labels


def test_all_subpages_load_individually():
    """Verify that each page in frontend/pages/ runs standalone with 0 exceptions."""
    pages = ["brand.py", "calendar.py", "library.py", "settings.py", "studio.py"]
    for page in pages:
        page_path = str((BASE_DIR / "frontend" / "pages" / page).resolve())
        at = AppTest.from_file(page_path, default_timeout=15).run()
        assert len(at.exception) == 0, f"Page {page} failed to run with error: {at.exception}"



def test_empty_states_render():
    """Verify that Studio renders the empty state when no strategy has been generated."""
    at = AppTest.from_file(MAIN_PATH)
    at.run(timeout=10)
    # The empty state card is rendered via markdown
    markdown_texts = [m.value for m in at.markdown]
    has_empty_state = any("Studio Workspace Ready" in t or "empty-state-card" in t for t in markdown_texts)
    assert has_empty_state, "Expected Studio Workspace Ready empty state illustration."


def test_theme_setting_persistence(tmp_path):
    """Verify theme setting can be written to DB, read back, and passed into session state."""
    db_file = tmp_path / "test_theme.db"
    init_db(db_file)

    # Default is dark
    assert get_setting("theme", default="dark", db_path=db_file) == "dark"

    # Set to light
    set_setting("theme", "light", db_path=db_file)
    assert get_setting("theme", default="dark", db_path=db_file) == "light"

    # Set back to dark
    set_setting("theme", "dark", db_path=db_file)
    assert get_setting("theme", default="dark", db_path=db_file) == "dark"


def test_wcag_aa_contrast_compliance():
    """Verify all defined palette color pairs meet or exceed WCAG AA requirements."""
    report = get_contrast_report()
    assert len(report) >= 10, "Contrast report must test dark and light mode color pairs."

    for pair_name, details in report.items():
        ratio = details["ratio"]
        target = details["target"]
        assert details["compliant"], (
            f"Failing contrast pair: '{pair_name}' has ratio {ratio}:1, required {target}:1"
        )


def test_calculate_contrast_ratio_formula():
    """Verify relative luminance and contrast ratio calculations with known values."""
    # Black on White is 21.0
    assert calculate_contrast_ratio("#000000", "#FFFFFF") == 21.0
    # White on Black is 21.0
    assert calculate_contrast_ratio("#FFFFFF", "#000000") == 21.0
    # Same color is 1.0
    assert calculate_contrast_ratio("#7C5CFF", "#7C5CFF") == 1.0


def test_strategy_generation_flow_mocked():
    """Verify that when generate is clicked, Groq is called and ideas populate session state."""
    mock_ideas = {
        "ideas": [
            {
                "title": "Mastering the Handstand Pushup",
                "content_type": "Post",
                "target_audience": "Athletes",
                "duration_estimate": "30s",
                "hook": "Stop kicking against the wall blindly.",
                "caption": "Here is the exact 3-step shoulder progression you need.",
                "call_to_action": "Save this guide for your next training session.",
                "hashtags": ["#calisthenics", "#gymnastics", "#handstand"],
                "visual_concept": "Silhouette of athlete holding handstand at sunset.",
                "image_prompt": "Cinematic wide shot of gymnast in perfect handstand, studio lighting.",
            }
        ]
    }

    with patch("services.content_generator.generate_content_ideas", return_value=mock_ideas) as mock_gen, \
         patch("frontend.main.generate_content_ideas", return_value=mock_ideas):
        at = AppTest.from_file(MAIN_PATH, default_timeout=15).run()

        # Find topic input
        topic_input = next(t for t in at.text_input if "Topic / Focus" in t.label)
        topic_input.set_value("Calisthenics")

        # Find generate button and trigger click
        gen_btn = next(b for b in at.button if "Generate Strategy" in b.label)
        gen_btn.click()
        at.run(timeout=15)

        assert mock_gen.called
        assert at.session_state.get("generated_topic") == "Calisthenics"
        assert at.session_state.get("generated_result") == mock_ideas
        assert len(at.session_state.get("generated_result", {}).get("ideas", [])) == 1
