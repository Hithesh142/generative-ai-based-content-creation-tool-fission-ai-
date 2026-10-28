"""
Unit test suite for Phase 4: Planning + Professional AI Features
Tests:
- Database migration 2 (scheduled_date, scheduled_time, brand_profiles)
- Calendar queries (overdue count, upcoming count, date range filtering, reschedule)
- Brand profile CRUD & active selection
- Brand guidelines injection into Groq & image prompts
- Tiered hashtag generator (niche, trending, branded tiers, deduplication, platform limits)
- Content plan generator parsing (7-day plan) & calendar batch scheduling
- Hook variants (5 psychological angles)
- Caption rewriter (styles and translation)
- Content quality score (0-100 rubric & heuristic disclaimer)
- Content repurposing across platforms
- RFC 5545 iCalendar (.ics) export validity & CSV calendar export
- Secret redacting logger
"""

import codecs
import datetime
import io
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest

from config.logging_config import SecretRedactingFormatter, get_logger
from database.db import (
    create_brand_profile,
    create_item,
    delete_brand_profile,
    get_active_brand_profile,
    get_brand_profile,
    get_calendar_metrics,
    get_db,
    init_db,
    list_brand_profiles,
    list_calendar_items,
    set_active_brand_profile,
    update_brand_profile,
    update_schedule,
)
from services.ai_tools import (
    CaptionRewriteResponse,
    ContentPlanItem,
    ContentPlanResponse,
    ContentQualityResponse,
    HashtagTiersResponse,
    HookVariant,
    HookVariantsResponse,
    RepurposeResponse,
    evaluate_content_quality,
    format_brand_guidelines,
    generate_content_plan,
    generate_hashtags,
    generate_hook_variants,
    repurpose_content,
    rewrite_caption,
)
from services.content_generator import generate_content_ideas
from services.exporter import export_calendar_as_csv, export_calendar_as_ics
from services.image_generator import enhance_image_prompt


@pytest.fixture
def temp_db(tmp_path):
    """Fixture providing an isolated SQLite database path with all migrations applied."""
    db_file = tmp_path / "test_phase4.db"
    init_db(db_file)
    return db_file


@pytest.fixture
def sample_brand_profile():
    return {
        "name": "Apex Athletics",
        "voice": "High-performance, science-backed, uncompromising",
        "language": "English",
        "target_market": "Elite athletes & fitness professionals",
        "audience_age_group": "22-40",
        "brand_colors": "#00B4D8 (electric cyan) and #03045E (deep navy)",
        "business_objective": "Drive coaching memberships and equipment sales",
        "words_to_avoid": "quick fix, miracle, easy, cheat code",
        "preferred_cta_style": "Direct challenge with action verb",
        "is_active": True,
    }


# ============================================================
# 1. DATABASE MIGRATION 2 & CALENDAR QUERIES
# ============================================================

def test_migration_2_and_calendar_columns(temp_db):
    """Verify that migration 2 added scheduled_date, scheduled_time, and brand_profiles table."""
    with get_db(temp_db) as conn:
        # Check schema version is at least 2
        cursor = conn.execute("SELECT MAX(version) FROM schema_version;")
        assert cursor.fetchone()[0] >= 2

        # Verify content_items has scheduled columns
        cursor = conn.execute("PRAGMA table_info(content_items);")
        cols = {r["name"] for r in cursor.fetchall()}
        assert "scheduled_date" in cols
        assert "scheduled_time" in cols

        # Verify brand_profiles table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='brand_profiles';")
        assert cursor.fetchone() is not None


def test_calendar_queries_and_metrics(temp_db):
    """Test calendar metrics (overdue, upcoming, unscheduled) and date range filtering."""
    today = datetime.date.today()
    past_date = (today - datetime.timedelta(days=2)).isoformat()
    future_date = (today + datetime.timedelta(days=3)).isoformat()

    # 1. Overdue item (scheduled in past, status Draft)
    create_item({
        "title": "Past Unposted Idea",
        "scheduled_date": past_date,
        "status": "Draft",
    }, db_path=temp_db)

    # 2. Upcoming item (scheduled in future, status Ready)
    create_item({
        "title": "Future Idea",
        "scheduled_date": future_date,
        "status": "Ready",
    }, db_path=temp_db)

    # 3. Unscheduled item
    create_item({
        "title": "Backlog Idea",
        "status": "Draft",
    }, db_path=temp_db)

    metrics = get_calendar_metrics(today_date=today.isoformat(), db_path=temp_db)
    assert metrics["overdue"] == 1
    assert metrics["upcoming"] == 1
    assert metrics["unscheduled"] == 1
    assert metrics["total_scheduled"] == 2

    # Test list_calendar_items range
    items_in_range = list_calendar_items(start_date=today.isoformat(), db_path=temp_db)
    assert len(items_in_range) == 1
    assert items_in_range[0]["title"] == "Future Idea"


def test_update_schedule(temp_db):
    """Test scheduling and rescheduling items."""
    item_id = create_item({"title": "Flexible Post"}, db_path=temp_db)
    assert update_schedule(item_id, "2026-11-15", "14:30", db_path=temp_db) is True

    items = list_calendar_items(start_date="2026-11-01", db_path=temp_db)
    assert len(items) == 1
    assert items[0]["scheduled_date"] == "2026-11-15"
    assert items[0]["scheduled_time"] == "14:30"


# ============================================================
# 2. BRAND PROFILES
# ============================================================

def test_brand_profile_crud(temp_db, sample_brand_profile):
    """Test brand profile creation, listing, active toggle, update, and delete."""
    prof_id = create_brand_profile(sample_brand_profile, db_path=temp_db)
    assert prof_id is not None

    # Verify active profile retrieval
    active = get_active_brand_profile(db_path=temp_db)
    assert active is not None
    assert active["name"] == "Apex Athletics"
    assert active["is_active"] is True
    assert "quick fix" in active["words_to_avoid"]

    # Create second profile as active (should deactivate the first)
    second_id = create_brand_profile({
        "name": "Zenith Wellness",
        "voice": "Calm, holistic, mindful",
        "is_active": True,
    }, db_path=temp_db)

    active_now = get_active_brand_profile(db_path=temp_db)
    assert active_now["name"] == "Zenith Wellness"

    # Switch active back to first
    assert set_active_brand_profile(prof_id, db_path=temp_db) is True
    active_reverted = get_active_brand_profile(db_path=temp_db)
    assert active_reverted["name"] == "Apex Athletics"

    # Delete second
    assert delete_brand_profile(second_id, db_path=temp_db) is True
    assert len(list_brand_profiles(db_path=temp_db)) == 1


def test_brand_guidelines_injection_into_prompt(sample_brand_profile):
    """Verify that brand voice, forbidden words, and colors are formatted into prompts."""
    formatted = format_brand_guidelines(sample_brand_profile)
    assert "Apex Athletics" in formatted
    assert "High-performance" in formatted
    assert "quick fix, miracle, easy, cheat code" in formatted
    assert "#00B4D8" in formatted


def test_enhance_prompt_with_brand_colors(sample_brand_profile):
    """Verify brand colors are passed into image prompt enhancer system instructions."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Athletic champion in a high-tech studio with neon cyan lighting"
    mock_resp = MagicMock(choices=[mock_choice])

    with patch("services.image_generator.get_groq_api_key", return_value="gsk_test"):
        with patch("groq.Groq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create.return_value = mock_resp

            enhanced = enhance_image_prompt(
                prompt="Athlete doing sprints",
                brand_profile=sample_brand_profile
            )
            assert len(enhanced) > 0

            # Verify system instruction contains brand colors
            call_kwargs = instance.chat.completions.create.call_args[1]
            messages = call_kwargs["messages"]
            system_msg = messages[0]["content"]
            assert "#00B4D8" in system_msg


# ============================================================
# 3. TIERED HASHTAG GENERATOR
# ============================================================

def test_hashtag_generator_tiers_and_deduplication():
    """Test hashtag generator tiers, deduplication, and platform limit enforcement."""
    mock_json = {
        "niche_hashtags": ["#calisthenicsmovement", "#pullupchallenge", "#sharedtag"],
        "trending_hashtags": ["#fitness", "#bodyweight", "#sharedtag"],
        "branded_hashtags": ["#apexathletics", "#sharedtag"],
    }
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(mock_json)
    mock_resp = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    # Test LinkedIn limit (5 tags max)
    res_li = generate_hashtags(
        topic="Calisthenics",
        platform="LinkedIn",
        client=mock_client
    )
    assert len(res_li.all_hashtags) <= 5
    assert len(set(res_li.all_hashtags)) == len(res_li.all_hashtags)  # Deduplicated

    # Test Twitter limit (3 tags max)
    res_tw = generate_hashtags(
        topic="Calisthenics",
        platform="Twitter",
        client=mock_client
    )
    assert len(res_tw.all_hashtags) <= 3


# ============================================================
# 4. CONTENT PLAN GENERATOR (7-Day Plan)
# ============================================================

def test_content_plan_generator_parsing():
    """Test generating a structured 7-day content plan."""
    plan_mock = {
        "topic": "Functional Strength",
        "duration_days": 7,
        "strategy_summary": "7-day progressive strength series",
        "plan": [
            {
                "day": d,
                "title": f"Day {d} Strength Principle",
                "platform": "Instagram",
                "content_type": "Carousel" if d % 2 == 0 else "Post",
                "hook": f"The #1 mistake in day {d} training.",
                "caption": f"Detailed training breakdown for day {d}.",
                "cta": "Save for later!",
                "hashtags": ["#strength", "#workout"],
                "visual_concept": "Athlete exercising",
                "image_prompt": "Cinematic workout shot 8k",
            }
            for d in range(1, 8)
        ]
    }
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(plan_mock)
    mock_resp = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    res = generate_content_plan(
        topic="Functional Strength",
        duration_days=7,
        client=mock_client
    )

    assert isinstance(res, ContentPlanResponse)
    assert res.duration_days == 7
    assert len(res.plan) == 7
    assert res.plan[0].day == 1
    assert res.plan[6].day == 7


# ============================================================
# 5. HOOK VARIANTS (5 Psychological Angles)
# ============================================================

def test_hook_variants_generator():
    """Test generating 5 distinct psychological hook variants."""
    hooks_mock = {
        "variants": [
            {"angle": "Curiosity Gap", "hook": "The silent form error killing your deadlift.", "rationale": "Creates mystery."},
            {"angle": "Contrarian", "hook": "Why stretching before lifting is making you weaker.", "rationale": "Challenges status quo."},
            {"angle": "Problem-Agitation", "hook": "Tired of lower back ache after leg day?", "rationale": "Hits resonant pain point."},
            {"angle": "Data / Proof", "hook": "How 3 sets of this added 20kg to my squat.", "rationale": "Provides authoritative numbers."},
            {"angle": "Direct Transformation", "hook": "Fix your pull-up form in under 60 seconds.", "rationale": "Fast direct value."},
        ]
    }
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(hooks_mock)
    mock_resp = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    res = generate_hook_variants(
        idea={"title": "Squat Mastery", "hook": "Learn to squat", "caption": "..." },
        client=mock_client
    )

    assert len(res.variants) == 5
    angles = [v.angle for v in res.variants]
    assert "Curiosity Gap" in angles
    assert "Contrarian" in angles


# ============================================================
# 6. CAPTION REWRITER
# ============================================================

def test_caption_rewriter():
    """Test caption rewriting for brevity and style."""
    rewrite_mock = {
        "original_caption": "Long rambling caption about gym motivation...",
        "rewritten_caption": "Consistency beats intensity. Every single time.",
        "style": "bold",
        "language": "English",
        "changes_summary": "Cut 80% words for punchy command.",
    }
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(rewrite_mock)
    mock_resp = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    res = rewrite_caption(
        caption="Long rambling caption about gym motivation...",
        style="bold",
        client=mock_client
    )

    assert res.style == "bold"
    assert "Consistency beats intensity" in res.rewritten_caption


# ============================================================
# 7. CONTENT QUALITY SCORE
# ============================================================

def test_content_quality_score():
    """Test quality score evaluation and disclaimer presence."""
    score_mock = {
        "overall_score": 88,
        "hook_strength": 90,
        "clarity_and_readability": 85,
        "cta_effectiveness": 80,
        "platform_fit": 95,
        "strengths": ["Magnetic opening hook", "Clear scannable formatting"],
        "weaknesses": ["CTA could be more specific"],
        "actionable_suggestions": ["Specify what exact action to take in the CTA"],
    }
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(score_mock)
    mock_resp = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    res = evaluate_content_quality(
        item={"title": "Test", "hook": "Great hook", "caption": "Great caption", "cta": "Follow"},
        client=mock_client
    )

    assert res.overall_score == 88
    assert res.hook_strength == 90
    assert "AI Quality Estimate" in res.disclaimer


# ============================================================
# 8. REPURPOSE CONTENT
# ============================================================

def test_repurpose_content():
    """Test adapting an idea to other platforms."""
    repurpose_mock = {
        "original_title": "Deadlift Form Guide",
        "repurposed_ideas": [
            {
                "platform": "LinkedIn",
                "content_type": "Article",
                "title": "Leadership Lessons from Heavy Deadlifts",
                "hook": "Lifting 500 lbs taught me how to manage stress under pressure.",
                "caption": "Professional breakdown...",
                "cta": "Connect for more executive health insights.",
                "hashtags": ["#leadership", "#resilience"],
                "visual_concept": "Executive at desk",
                "image_prompt": "Cinematic modern executive office 8k",
            },
            {
                "platform": "Twitter",
                "content_type": "Thread",
                "title": "5 Deadlift Cues (Thread)",
                "hook": "Most people ruin their lower backs doing this:",
                "caption": "1/5 Set your feet...",
                "cta": "RT if this helped your form.",
                "hashtags": ["#fitness", "#lift"],
                "visual_concept": "Minimalist form diagram",
                "image_prompt": "Vector biomechanics illustration",
            }
        ]
    }
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(repurpose_mock)
    mock_resp = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    res = repurpose_content(
        item={"title": "Deadlift Form Guide", "hook": "Fix your form", "caption": "Body copy"},
        target_platforms=["LinkedIn", "Twitter"],
        client=mock_client
    )

    assert len(res.repurposed_ideas) == 2
    platforms = [i.platform for i in res.repurposed_ideas]
    assert "LinkedIn" in platforms
    assert "Twitter" in platforms


# ============================================================
# 9. CALENDAR EXPORTS (RFC 5545 iCalendar & CSV)
# ============================================================

def test_export_calendar_as_ics():
    """Test RFC 5545 iCalendar generation for Google/Apple Calendar."""
    items = [
        {
            "id": "post-101",
            "title": "Launch Teaser",
            "platform": "Instagram",
            "content_type": "Reel",
            "status": "Ready",
            "scheduled_date": "2026-11-20",
            "scheduled_time": "15:00",
            "hook": "Something big arrives Friday.",
            "caption": "Get ready for the release.",
            "cta": "Link in bio to RSVP.",
        },
        {
            "id": "post-102",
            "title": "Full Feature Walkthrough",
            "platform": "YouTube",
            "content_type": "Video",
            "status": "Planned",
            "scheduled_date": "2026-11-22",
            "scheduled_time": None,  # Full-day event
            "hook": "Full walkthrough of the new system.",
            "caption": "Deep dive tutorial.",
            "cta": "Subscribe for updates.",
        }
    ]

    ics_content = export_calendar_as_ics(items)

    assert "BEGIN:VCALENDAR" in ics_content
    assert "VERSION:2.0" in ics_content
    assert "PRODID:-//Fission AI//Content Calendar 1.0//EN" in ics_content
    assert "BEGIN:VEVENT" in ics_content
    assert "SUMMARY:[Instagram] Launch Teaser" in ics_content
    assert "DTSTART:20261120T150000Z" in ics_content
    assert "DTSTART;VALUE=DATE:20261122" in ics_content
    assert "END:VEVENT" in ics_content
    assert "END:VCALENDAR" in ics_content


def test_export_calendar_as_csv():
    """Test calendar CSV export with UTF-8 BOM."""
    items = [
        {
            "id": "post-201",
            "title": "Tech Stack Deep Dive",
            "platform": "LinkedIn",
            "content_type": "Article",
            "status": "Planned",
            "scheduled_date": "2026-12-01",
            "scheduled_time": "09:00",
            "hook": "Why we chose SQLite over PostgreSQL.",
            "caption": "Architectural breakdown...",
            "cta": "Join the discussion.",
            "hashtags": ["#tech", "#architecture"],
        }
    ]

    csv_bytes = export_calendar_as_csv(items)
    assert csv_bytes.startswith(codecs.BOM_UTF8)
    csv_text = csv_bytes.decode("utf-8-sig")
    assert "Tech Stack Deep Dive" in csv_text
    assert "2026-12-01" in csv_text
    assert "09:00" in csv_text


# ============================================================
# 10. SECRET REDACTING LOGGER
# ============================================================

def test_secret_redacting_formatter():
    """Verify that logger formatter redacts Groq and HF secrets."""
    formatter = SecretRedactingFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Calling Groq with key gsk_abcdef1234567890abcdef123456 and HF token hf_1234567890abcdef1234567890",
        args=(),
        exc_info=None
    )

    formatted = formatter.format(record)
    assert "gsk_***REDACTED***" in formatted
    assert "hf_***REDACTED***" in formatted
    assert "gsk_abcdef" not in formatted
    assert "hf_12345" not in formatted
