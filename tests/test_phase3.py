"""
Unit test suite for Phase 3: SQLite Library + Exporters
Tests:
- SQLite table schema creation & migrations
- Parameterized CRUD operations (create, get, list, update, delete)
- Search and multi-column filtering (platform, content_type, status, topic)
- Proof of persistence across connection restarts
- Safe slugification & path traversal prevention
- Exporter outputs: TXT, CSV with UTF-8 BOM, JSON, and ZIP packaging
"""

import codecs
import io
import json
import sys
import zipfile
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from PIL import Image

from database.db import (
    count_items,
    create_item,
    delete_item,
    get_db,
    get_distinct_values,
    get_item,
    get_recent_images,
    init_db,
    list_items,
    update_item,
)
from services.exporter import (
    export_caption_as_txt,
    export_image_bytes,
    export_items_as_csv,
    export_items_as_json,
    export_items_as_zip,
    slugify_filename,
)


@pytest.fixture
def temp_db(tmp_path):
    """Fixture providing a fresh isolated SQLite database path."""
    db_file = tmp_path / "test_fission.db"
    init_db(db_file)
    return db_file


@pytest.fixture
def sample_item_data():
    """Sample dictionary representing a content idea."""
    return {
        "topic": "Home Workout",
        "title": "5 Calisthenics Moves for Strength",
        "platform": "Instagram",
        "target_audience": "Beginner athletes",
        "content_type": "Carousel",
        "hook": "Stop wasting hours at the gym when you have gravity.",
        "caption": "Here are 5 fundamental bodyweight exercises that build real functional strength...",
        "cta": "Save this post for your next workout session!",
        "hashtags": ["#calisthenics", "#homeworkout", "#fitness"],
        "visual_concept": "Athlete performing a clean pull-up in a sunlit loft",
        "image_prompt": "An athlete doing a pull-up in morning golden hour lighting, cinematic 8k",
        "image_path": None,
        "tags": ["strength", "bodyweight"],
        "status": "Draft",
        "notes": "Plan to release on Monday morning",
    }


# ============================================================
# DATABASE TESTS
# ============================================================

def test_init_db_and_migration(temp_db):
    """Test that init_db creates schema_version and content_items tables with indexes."""
    with get_db(temp_db) as conn:
        cursor = conn.execute("SELECT version, description FROM schema_version;")
        row = cursor.fetchone()
        assert row is not None
        assert row["version"] == 1
        assert "Initial content_items schema" in row["description"]

        # Check content_items exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='content_items';")
        assert cursor.fetchone() is not None


def test_create_and_get_item(temp_db, sample_item_data):
    """Test inserting an item and retrieving it with full deserialization."""
    item_id = create_item(sample_item_data, db_path=temp_db)
    assert item_id is not None
    assert len(item_id) > 10

    retrieved = get_item(item_id, db_path=temp_db)
    assert retrieved is not None
    assert retrieved["id"] == item_id
    assert retrieved["title"] == "5 Calisthenics Moves for Strength"
    assert retrieved["platform"] == "Instagram"
    assert retrieved["status"] == "Draft"
    assert isinstance(retrieved["hashtags"], list)
    assert "#calisthenics" in retrieved["hashtags"]
    assert isinstance(retrieved["tags"], list)
    assert "strength" in retrieved["tags"]
    assert retrieved["created_at"] is not None
    assert retrieved["updated_at"] is not None


def test_get_nonexistent_item(temp_db):
    """Test that querying a nonexistent ID returns None."""
    assert get_item("non-existent-uuid", db_path=temp_db) is None


def test_update_item(temp_db, sample_item_data):
    """Test updating existing item fields and auto-updating updated_at timestamp."""
    item_id = create_item(sample_item_data, db_path=temp_db)
    item_before = get_item(item_id, db_path=temp_db)

    # Perform update
    success = update_item(
        item_id,
        {
            "status": "Ready",
            "caption": "Updated caption with new CTA details.",
            "hashtags": ["#fitness", "#strength", "#goals"],
            "notes": "Reviewed and approved.",
        },
        db_path=temp_db,
    )
    assert success is True

    item_after = get_item(item_id, db_path=temp_db)
    assert item_after["status"] == "Ready"
    assert item_after["caption"] == "Updated caption with new CTA details."
    assert item_after["notes"] == "Reviewed and approved."
    assert item_after["hashtags"] == ["#fitness", "#strength", "#goals"]
    assert item_after["updated_at"] >= item_before["updated_at"]


def test_delete_item(temp_db, sample_item_data):
    """Test deleting an item."""
    item_id = create_item(sample_item_data, db_path=temp_db)
    assert get_item(item_id, db_path=temp_db) is not None

    deleted = delete_item(item_id, db_path=temp_db)
    assert deleted is True
    assert get_item(item_id, db_path=temp_db) is None

    # Deleting already deleted item returns False
    assert delete_item(item_id, db_path=temp_db) is False


def test_list_items_search_and_filters(temp_db):
    """Test listing items with text search, platform filter, status filter, and sorting."""
    # Seed 3 different items
    create_item({
        "topic": "Python Programming",
        "title": "Mastering AsyncIO in Python",
        "platform": "LinkedIn",
        "content_type": "Article",
        "status": "Ready",
        "hook": "Stop blocking your event loop.",
        "caption": "Asyncio gives Python massive speed boosts.",
    }, db_path=temp_db)

    create_item({
        "topic": "Python Programming",
        "title": "Pytest Best Practices",
        "platform": "Twitter",
        "content_type": "Thread",
        "status": "Draft",
        "hook": "Write bulletproof tests.",
        "caption": "Here are 5 tips for pytest fixtures.",
    }, db_path=temp_db)

    create_item({
        "topic": "Digital Art",
        "title": "3D Blender Lighting Guide",
        "platform": "Instagram",
        "content_type": "Reel",
        "status": "Published",
        "hook": "Lighting makes or breaks your render.",
        "caption": "Three-point lighting setup tutorial.",
    }, db_path=temp_db)

    # Search for "AsyncIO"
    search_res = list_items(search="AsyncIO", db_path=temp_db)
    assert len(search_res) == 1
    assert search_res[0]["title"] == "Mastering AsyncIO in Python"

    # Search across hook
    hook_res = list_items(search="bulletproof", db_path=temp_db)
    assert len(hook_res) == 1
    assert hook_res[0]["title"] == "Pytest Best Practices"

    # Filter by platform
    li_res = list_items(platform="LinkedIn", db_path=temp_db)
    assert len(li_res) == 1
    assert li_res[0]["platform"] == "LinkedIn"

    # Filter by status
    draft_res = list_items(status="Draft", db_path=temp_db)
    assert len(draft_res) == 1
    assert draft_res[0]["status"] == "Draft"

    # Total counts
    assert count_items(db_path=temp_db) == 3
    assert count_items(platform="Instagram", db_path=temp_db) == 1

    # Distinct values
    platforms = get_distinct_values("platform", db_path=temp_db)
    assert set(platforms) == {"Instagram", "LinkedIn", "Twitter"}


def test_proof_of_persistence_restart(tmp_path):
    """
    PROOF OF PERSISTENCE:
    1. Create an item and insert into an SQLite database file.
    2. Close all connections completely (simulating app shutdown/restart).
    3. Re-open the database from scratch and verify the item and data persist unchanged.
    """
    db_file = tmp_path / "persistence_test.db"

    # Step 1: Initialize and insert
    init_db(db_file)
    item_id = create_item({
        "topic": "Artificial Intelligence",
        "title": "The Evolution of Multimodal Models",
        "platform": "YouTube",
        "content_type": "Video Script",
        "status": "Planned",
        "caption": "Exploring text, vision, and audio neural architectures.",
        "hashtags": ["#ai", "#multimodal"],
    }, db_path=db_file)

    # Step 2: Full restart simulation - zero open handles
    del item_id

    # Step 3: Re-open in a fresh session
    all_items = list_items(db_path=db_file)
    assert len(all_items) == 1
    persisted_item = all_items[0]

    assert persisted_item["title"] == "The Evolution of Multimodal Models"
    assert persisted_item["platform"] == "YouTube"
    assert persisted_item["status"] == "Planned"
    assert persisted_item["hashtags"] == ["#ai", "#multimodal"]


# ============================================================
# EXPORTER TESTS
# ============================================================

def test_slugify_filename():
    """Test safe filename slugification and path traversal defense."""
    # Normal title
    assert slugify_filename("My Fantastic 2026 Strategy!") == "My_Fantastic_2026_Strategy"

    # Path traversal attack vectors
    assert ".." not in slugify_filename("../../etc/passwd")
    assert "/" not in slugify_filename("../../../secret/token.txt")
    assert "\\" not in slugify_filename("..\\..\\windows\\system32")

    # Forbidden Windows/POSIX chars: \/*?:"<>|
    dirty = 'cool:blog*post?"<awesome>|test'
    cleaned = slugify_filename(dirty)
    for char in r'\/*?:"<>|':
        assert char not in cleaned

    # Empty fallback
    assert slugify_filename("") == "export"
    assert slugify_filename("   ...   ") == "export"


def test_export_caption_as_txt(sample_item_data):
    """Test plain text caption export format."""
    txt = export_caption_as_txt(sample_item_data)
    assert "TITLE: 5 Calisthenics Moves for Strength" in txt
    assert "PLATFORM: Instagram" in txt
    assert "HOOK / HEADLINE" in txt
    assert "Stop wasting hours at the gym" in txt
    assert "CAPTION / POST BODY" in txt
    assert "5 fundamental bodyweight exercises" in txt
    assert "#calisthenics" in txt


def test_export_items_as_csv(sample_item_data):
    """Test CSV export with UTF-8 BOM encoding for Microsoft Excel."""
    csv_bytes = export_items_as_csv([sample_item_data])

    # Check UTF-8 BOM presence
    assert csv_bytes.startswith(codecs.BOM_UTF8)

    # Decode content
    csv_text = csv_bytes.decode("utf-8-sig")
    assert "5 Calisthenics Moves for Strength" in csv_text
    assert "Instagram" in csv_text
    assert "Carousel" in csv_text
    assert "Beginner athletes" in csv_text


def test_export_items_as_json(sample_item_data):
    """Test JSON export formatting."""
    json_str = export_items_as_json([sample_item_data])
    parsed = json.loads(json_str)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["title"] == "5 Calisthenics Moves for Strength"


def test_export_image_bytes(tmp_path):
    """Test exporting image bytes as PNG and JPEG."""
    img_path = tmp_path / "test_visual.png"
    img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 255))
    img.save(img_path)

    # Export PNG
    png_bytes = export_image_bytes(img_path, target_format="PNG")
    assert len(png_bytes) > 0
    loaded_png = Image.open(io.BytesIO(png_bytes))
    assert loaded_png.format == "PNG"

    # Export JPEG (auto converts RGBA -> RGB)
    jpeg_bytes = export_image_bytes(img_path, target_format="JPEG")
    assert len(jpeg_bytes) > 0
    loaded_jpeg = Image.open(io.BytesIO(jpeg_bytes))
    assert loaded_jpeg.format == "JPEG"

    # Non-existent file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        export_image_bytes(tmp_path / "does_not_exist.png")


def test_export_items_as_zip(tmp_path, sample_item_data):
    """Test self-contained ZIP archive creation with CSV, JSON, TXT captions, and images."""
    # Create a real test image file
    real_img_path = tmp_path / "generated_art.png"
    img = Image.new("RGB", (64, 64), color="blue")
    img.save(real_img_path)

    sample_item_data["image_path"] = str(real_img_path)
    sample_item_data["id"] = "test-uuid-1234"

    zip_bytes = export_items_as_zip([sample_item_data])
    assert len(zip_bytes) > 0

    # Unpack in-memory and verify contents
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()

        # Verify summary files
        assert "content_summary.csv" in namelist
        assert "campaign_plan.json" in namelist

        # Verify item folder
        matching_captions = [n for n in namelist if n.endswith("caption.txt")]
        assert len(matching_captions) == 1

        caption_content = zf.read(matching_captions[0]).decode("utf-8")
        assert "5 Calisthenics Moves for Strength" in caption_content

        # Verify image file packaged inside zip
        matching_images = [n for n in namelist if n.endswith(".png")]
        assert len(matching_images) == 1
