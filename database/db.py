"""
Fission AI - SQLite Database Module
Provides parameterized CRUD operations, migrations, and query utilities for:
- content_items (with scheduling, status, visual paths, and JSON tags)
- brand_profiles (voice, colors, words to avoid, CTA style, active selection)
- calendar queries (week/month views, overdue & upcoming metrics)
Ensures zero SQL injection vulnerabilities and resilient persistence across application restarts.
"""

import datetime
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from config.settings import DB_PATH, IMAGES_DIR

# Allowed status values
ALLOWED_STATUSES = {"Draft", "Planned", "Ready", "Published"}

# Whitelist of columns allowed for sorting content_items
ALLOWED_SORT_COLUMNS = {
    "created_at",
    "updated_at",
    "title",
    "platform",
    "status",
    "topic",
    "content_type",
    "scheduled_date",
}
ALLOWED_SORT_ORDERS = {"ASC", "DESC"}

# Whitelist of updatable columns in content_items
UPDATABLE_COLUMNS = {
    "topic",
    "title",
    "platform",
    "target_audience",
    "content_type",
    "hook",
    "caption",
    "cta",
    "hashtags",
    "visual_concept",
    "image_prompt",
    "image_path",
    "tags",
    "status",
    "notes",
    "scheduled_date",
    "scheduled_time",
}

# Whitelist of updatable columns in brand_profiles
BRAND_PROFILE_UPDATABLE_COLUMNS = {
    "name",
    "voice",
    "language",
    "target_market",
    "audience_age_group",
    "brand_colors",
    "business_objective",
    "words_to_avoid",
    "preferred_cta_style",
    "is_active",
}


def _resolve_db_path(db_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve and ensure the parent directory for the database path."""
    target_path = Path(db_path) if db_path else DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return target_path


@contextmanager
def get_db(db_path: Optional[Union[str, Path]] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager yielding a thread-safe SQLite connection configured with WAL mode
    and Row factory. Automatically commits on completion and rolls back on exception.
    """
    path = _resolve_db_path(db_path)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# SCHEMA MIGRATIONS
# ============================================================

def init_db(db_path: Optional[Union[str, Path]] = None) -> None:
    """
    Initialize database schema and apply pending migrations sequentially.
    """
    path = _resolve_db_path(db_path)

    with get_db(path) as conn:
        # Create schema_version table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            );
        """)

        cursor = conn.execute("SELECT MAX(version) FROM schema_version;")
        row = cursor.fetchone()
        current_version = row[0] if (row and row[0] is not None) else 0

        # Migration 1: Base content_items schema
        if current_version < 1:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content_items (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    title TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    target_audience TEXT,
                    content_type TEXT NOT NULL,
                    hook TEXT,
                    caption TEXT,
                    cta TEXT,
                    hashtags TEXT,
                    visual_concept TEXT,
                    image_prompt TEXT,
                    image_path TEXT,
                    tags TEXT,
                    status TEXT NOT NULL DEFAULT 'Draft',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_topic ON content_items(topic);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_platform ON content_items(platform);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_status ON content_items(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_content_type ON content_items(content_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_created_at ON content_items(created_at);")

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?);",
                (1, now_iso, "Initial content_items schema with indexes"),
            )

        # Migration 2: Add calendar scheduling columns & brand_profiles table
        if current_version < 2:
            cursor = conn.execute("PRAGMA table_info(content_items);")
            existing_cols = {r["name"] for r in cursor.fetchall()}

            if "scheduled_date" not in existing_cols:
                conn.execute("ALTER TABLE content_items ADD COLUMN scheduled_date TEXT;")
            if "scheduled_time" not in existing_cols:
                conn.execute("ALTER TABLE content_items ADD COLUMN scheduled_time TEXT;")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_scheduled_date ON content_items(scheduled_date);")

            # Create brand_profiles table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS brand_profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    voice TEXT,
                    language TEXT DEFAULT 'English',
                    target_market TEXT,
                    audience_age_group TEXT,
                    brand_colors TEXT,
                    business_objective TEXT,
                    words_to_avoid TEXT,
                    preferred_cta_style TEXT,
                    is_active INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brand_profiles_active ON brand_profiles(is_active);")

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?);",
                (2, now_iso, "Add scheduled_date, scheduled_time, and brand_profiles table"),
            )

        # Migration 3: Add app_settings table (for persistent theme, UI state, etc.)
        if current_version < 3:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?);",
                (3, now_iso, "Add app_settings table for persistent UI preferences"),
            )


# ============================================================
# ROW SERIALIZATION / DESERIALIZATION HELPERS
# ============================================================

def _serialize_json_field(val: Any) -> str:
    """Safely serialize lists/dicts into JSON strings for SQLite storage."""
    if val is None:
        return "[]"
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, str):
        val_strip = val.strip()
        if (val_strip.startswith("[") and val_strip.endswith("]")) or (val_strip.startswith("{") and val_strip.endswith("}")):
            try:
                json.loads(val_strip)
                return val_strip
            except Exception:
                pass
        items = [p.strip() for p in val.replace(",", " ").split() if p.strip()]
        return json.dumps(items, ensure_ascii=False)
    return json.dumps([str(val)], ensure_ascii=False)


def _deserialize_item_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert an SQLite Row to a clean Python dictionary with parsed JSON fields."""
    item = dict(row)

    # Deserialize hashtags
    raw_hashtags = item.get("hashtags")
    if raw_hashtags:
        try:
            item["hashtags"] = json.loads(raw_hashtags)
        except Exception:
            item["hashtags"] = [h.strip() for h in raw_hashtags.split() if h.strip()]
    else:
        item["hashtags"] = []

    # Deserialize tags
    raw_tags = item.get("tags")
    if raw_tags:
        try:
            item["tags"] = json.loads(raw_tags)
        except Exception:
            item["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
    else:
        item["tags"] = []

    return item


def _deserialize_brand_profile_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a brand_profiles Row to dict."""
    prof = dict(row)
    prof["is_active"] = bool(prof.get("is_active", 0))
    return prof


# ============================================================
# CONTENT ITEMS CRUD OPERATIONS
# ============================================================

def create_item(
    item_data: Dict[str, Any],
    db_path: Optional[Union[str, Path]] = None,
) -> str:
    """
    Insert a new content item into the database using parameterized queries.
    Returns the generated or specified item ID (UUID string).
    """
    init_db(db_path)

    topic = str(item_data.get("topic", "")).strip() or "General"
    title = str(item_data.get("title", "")).strip() or "Untitled Concept"
    platform = str(item_data.get("platform", "")).strip() or "General"
    content_type = str(item_data.get("content_type", "")).strip() or "Post"

    item_id = str(item_data.get("id") or uuid.uuid4())
    status = str(item_data.get("status", "Draft")).strip().capitalize()
    if status not in ALLOWED_STATUSES:
        status = "Draft"

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    created_at = item_data.get("created_at") or now_iso
    updated_at = now_iso

    hashtags_json = _serialize_json_field(item_data.get("hashtags"))
    tags_json = _serialize_json_field(item_data.get("tags"))

    scheduled_date = item_data.get("scheduled_date") or None
    scheduled_time = item_data.get("scheduled_time") or None

    query = """
        INSERT INTO content_items (
            id, topic, title, platform, target_audience, content_type,
            hook, caption, cta, hashtags, visual_concept, image_prompt,
            image_path, tags, status, notes, scheduled_date, scheduled_time,
            created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?
        );
    """
    params = (
        item_id,
        topic,
        title,
        platform,
        item_data.get("target_audience") or None,
        content_type,
        item_data.get("hook") or None,
        item_data.get("caption") or None,
        item_data.get("cta") or None,
        hashtags_json,
        item_data.get("visual_concept") or None,
        item_data.get("image_prompt") or None,
        item_data.get("image_path") or None,
        tags_json,
        status,
        item_data.get("notes") or None,
        scheduled_date,
        scheduled_time,
        created_at,
        updated_at,
    )

    with get_db(db_path) as conn:
        conn.execute(query, params)

    return item_id


def get_item(
    item_id: str,
    db_path: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a single content item by ID."""
    init_db(db_path)
    query = "SELECT * FROM content_items WHERE id = ?;"

    with get_db(db_path) as conn:
        cursor = conn.execute(query, (str(item_id).strip(),))
        row = cursor.fetchone()
        if row:
            return _deserialize_item_row(row)
    return None


def list_items(
    search: Optional[str] = None,
    platform: Optional[str] = None,
    content_type: Optional[str] = None,
    status: Optional[str] = None,
    topic: Optional[str] = None,
    scheduled_only: bool = False,
    sort_by: str = "created_at",
    sort_order: str = "DESC",
    limit: int = 100,
    offset: int = 0,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """List content items with parameterized filters, pagination, and sorting."""
    init_db(db_path)

    clauses: List[str] = []
    params: List[Any] = []

    if search and search.strip():
        term = f"%{search.strip()}%"
        clauses.append("(topic LIKE ? OR title LIKE ? OR hook LIKE ? OR caption LIKE ?)")
        params.extend([term, term, term, term])

    if platform and platform.strip() and platform.strip().lower() != "all":
        clauses.append("platform = ?")
        params.append(platform.strip())

    if content_type and content_type.strip() and content_type.strip().lower() != "all":
        clauses.append("content_type = ?")
        params.append(content_type.strip())

    if status and status.strip() and status.strip().lower() != "all":
        clauses.append("status = ?")
        params.append(status.strip().capitalize())

    if topic and topic.strip() and topic.strip().lower() != "all":
        clauses.append("topic = ?")
        params.append(topic.strip())

    if scheduled_only:
        clauses.append("scheduled_date IS NOT NULL AND scheduled_date != ''")

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    col = sort_by if sort_by in ALLOWED_SORT_COLUMNS else "created_at"
    order = sort_order.upper() if sort_order.upper() in ALLOWED_SORT_ORDERS else "DESC"

    query = f"""
        SELECT * FROM content_items
        {where_sql}
        ORDER BY {col} {order}
        LIMIT ? OFFSET ?;
    """
    params.extend([max(1, int(limit)), max(0, int(offset))])

    with get_db(db_path) as conn:
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [_deserialize_item_row(r) for r in rows]


def count_items(
    search: Optional[str] = None,
    platform: Optional[str] = None,
    content_type: Optional[str] = None,
    status: Optional[str] = None,
    topic: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> int:
    """Return total count of items matching filters."""
    init_db(db_path)

    clauses: List[str] = []
    params: List[Any] = []

    if search and search.strip():
        term = f"%{search.strip()}%"
        clauses.append("(topic LIKE ? OR title LIKE ? OR hook LIKE ? OR caption LIKE ?)")
        params.extend([term, term, term, term])

    if platform and platform.strip() and platform.strip().lower() != "all":
        clauses.append("platform = ?")
        params.append(platform.strip())

    if content_type and content_type.strip() and content_type.strip().lower() != "all":
        clauses.append("content_type = ?")
        params.append(content_type.strip())

    if status and status.strip() and status.strip().lower() != "all":
        clauses.append("status = ?")
        params.append(status.strip().capitalize())

    if topic and topic.strip() and topic.strip().lower() != "all":
        clauses.append("topic = ?")
        params.append(topic.strip())

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    query = f"SELECT COUNT(*) FROM content_items {where_sql};"

    with get_db(db_path) as conn:
        cursor = conn.execute(query, tuple(params))
        row = cursor.fetchone()
        return row[0] if row else 0


def update_item(
    item_id: str,
    updates: Dict[str, Any],
    db_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Update fields of an existing content item using parameterized queries."""
    init_db(db_path)

    set_clauses: List[str] = []
    params: List[Any] = []

    for key, val in updates.items():
        if key not in UPDATABLE_COLUMNS:
            continue

        if key in ("hashtags", "tags"):
            val_serialized = _serialize_json_field(val)
            set_clauses.append(f"{key} = ?")
            params.append(val_serialized)
        elif key == "status":
            stat = str(val).strip().capitalize()
            if stat in ALLOWED_STATUSES:
                set_clauses.append("status = ?")
                params.append(stat)
        else:
            set_clauses.append(f"{key} = ?")
            params.append(val)

    if not set_clauses:
        return False

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    set_clauses.append("updated_at = ?")
    params.append(now_iso)

    params.append(str(item_id).strip())

    query = f"""
        UPDATE content_items
        SET {", ".join(set_clauses)}
        WHERE id = ?;
    """

    with get_db(db_path) as conn:
        cursor = conn.execute(query, tuple(params))
        return cursor.rowcount > 0


def delete_item(
    item_id: str,
    db_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Delete a content item by ID."""
    init_db(db_path)
    query = "DELETE FROM content_items WHERE id = ?;"

    with get_db(db_path) as conn:
        cursor = conn.execute(query, (str(item_id).strip(),))
        return cursor.rowcount > 0


def get_distinct_values(
    field: str,
    db_path: Optional[Union[str, Path]] = None,
) -> List[str]:
    """Retrieve distinct non-empty values for a given column."""
    init_db(db_path)
    allowed_fields = {"platform", "content_type", "status", "topic"}
    if field not in allowed_fields:
        raise ValueError(f"Field '{field}' is not allowed for distinct queries.")

    query = f"""
        SELECT DISTINCT {field}
        FROM content_items
        WHERE {field} IS NOT NULL AND {field} != ''
        ORDER BY {field} ASC;
    """

    with get_db(db_path) as conn:
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        return [str(r[0]) for r in rows if r[0]]


def get_recent_images(
    limit: int = 20,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve recent images from database items and existing disk storage."""
    init_db(db_path)
    results: List[Dict[str, Any]] = []
    seen_paths = set()

    query = """
        SELECT id, title, topic, image_path, created_at
        FROM content_items
        WHERE image_path IS NOT NULL AND image_path != ''
        ORDER BY updated_at DESC
        LIMIT ?;
    """
    with get_db(db_path) as conn:
        cursor = conn.execute(query, (limit,))
        for row in cursor.fetchall():
            path_str = str(row["image_path"]).strip()
            if Path(path_str).exists() and path_str not in seen_paths:
                seen_paths.add(path_str)
                results.append({
                    "item_id": row["id"],
                    "title": row["title"],
                    "topic": row["topic"],
                    "image_path": path_str,
                    "created_at": row["created_at"],
                })

    if len(results) < limit and IMAGES_DIR.exists():
        try:
            image_files = sorted(
                IMAGES_DIR.glob("*.png"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            for img_file in image_files:
                path_str = str(img_file.resolve())
                if path_str not in seen_paths:
                    seen_paths.add(path_str)
                    mtime = datetime.datetime.fromtimestamp(
                        img_file.stat().st_mtime,
                        tz=datetime.timezone.utc
                    ).isoformat()
                    results.append({
                        "item_id": None,
                        "title": img_file.stem,
                        "topic": "Recent Generation",
                        "image_path": path_str,
                        "created_at": mtime,
                    })
                if len(results) >= limit:
                    break
        except Exception:
            pass

    return results


# ============================================================
# CALENDAR PLANNING & METRICS
# ============================================================

def update_schedule(
    item_id: str,
    scheduled_date: Optional[str],
    scheduled_time: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Schedule or reschedule a content item to a specific date and time."""
    init_db(db_path)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    query = """
        UPDATE content_items
        SET scheduled_date = ?, scheduled_time = ?, updated_at = ?
        WHERE id = ?;
    """
    with get_db(db_path) as conn:
        cursor = conn.execute(query, (scheduled_date, scheduled_time, now_iso, str(item_id).strip()))
        return cursor.rowcount > 0


def list_calendar_items(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """List scheduled content items filtered by date range, platform, and status."""
    init_db(db_path)

    clauses: List[str] = ["scheduled_date IS NOT NULL AND scheduled_date != ''"]
    params: List[Any] = []

    if start_date:
        clauses.append("scheduled_date >= ?")
        params.append(start_date.strip())

    if end_date:
        clauses.append("scheduled_date <= ?")
        params.append(end_date.strip())

    if platform and platform.strip() and platform.strip().lower() != "all":
        clauses.append("platform = ?")
        params.append(platform.strip())

    if status and status.strip() and status.strip().lower() != "all":
        clauses.append("status = ?")
        params.append(status.strip().capitalize())

    where_sql = "WHERE " + " AND ".join(clauses)
    query = f"""
        SELECT * FROM content_items
        {where_sql}
        ORDER BY scheduled_date ASC, scheduled_time ASC;
    """

    with get_db(db_path) as conn:
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [_deserialize_item_row(r) for r in rows]


def get_calendar_metrics(
    today_date: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, int]:
    """
    Compute calendar health metrics:
    - overdue: scheduled_date < today AND status != 'Published'
    - upcoming: scheduled_date >= today AND status != 'Published'
    - published: status == 'Published'
    - unscheduled: scheduled_date IS NULL OR scheduled_date == ''
    - total_scheduled: count with scheduled_date
    """
    init_db(db_path)
    today = today_date or datetime.date.today().isoformat()

    with get_db(db_path) as conn:
        # Overdue
        cur = conn.execute(
            "SELECT COUNT(*) FROM content_items WHERE scheduled_date < ? AND status != 'Published' AND scheduled_date IS NOT NULL AND scheduled_date != '';",
            (today,)
        )
        overdue_cnt = cur.fetchone()[0]

        # Upcoming
        cur = conn.execute(
            "SELECT COUNT(*) FROM content_items WHERE scheduled_date >= ? AND status != 'Published' AND scheduled_date IS NOT NULL AND scheduled_date != '';",
            (today,)
        )
        upcoming_cnt = cur.fetchone()[0]

        # Published
        cur = conn.execute("SELECT COUNT(*) FROM content_items WHERE status = 'Published';")
        published_cnt = cur.fetchone()[0]

        # Unscheduled
        cur = conn.execute("SELECT COUNT(*) FROM content_items WHERE scheduled_date IS NULL OR scheduled_date = '';")
        unscheduled_cnt = cur.fetchone()[0]

        # Total scheduled
        cur = conn.execute("SELECT COUNT(*) FROM content_items WHERE scheduled_date IS NOT NULL AND scheduled_date != '';")
        total_scheduled = cur.fetchone()[0]

    return {
        "overdue": overdue_cnt,
        "upcoming": upcoming_cnt,
        "published": published_cnt,
        "unscheduled": unscheduled_cnt,
        "total_scheduled": total_scheduled,
    }


# ============================================================
# BRAND PROFILES CRUD
# ============================================================

def create_brand_profile(
    profile_data: Dict[str, Any],
    db_path: Optional[Union[str, Path]] = None,
) -> str:
    """Create a new brand profile."""
    init_db(db_path)

    profile_id = str(profile_data.get("id") or uuid.uuid4())
    name = str(profile_data.get("name", "Default Brand")).strip()
    voice = profile_data.get("voice") or None
    language = profile_data.get("language") or "English"
    target_market = profile_data.get("target_market") or None
    audience_age_group = profile_data.get("audience_age_group") or None
    brand_colors = profile_data.get("brand_colors") or None
    business_objective = profile_data.get("business_objective") or None
    words_to_avoid = profile_data.get("words_to_avoid") or None
    preferred_cta_style = profile_data.get("preferred_cta_style") or None
    is_active = 1 if profile_data.get("is_active") else 0

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with get_db(db_path) as conn:
        if is_active:
            # Clear other active profiles so only 1 profile is active
            conn.execute("UPDATE brand_profiles SET is_active = 0;")

        query = """
            INSERT INTO brand_profiles (
                id, name, voice, language, target_market, audience_age_group,
                brand_colors, business_objective, words_to_avoid, preferred_cta_style,
                is_active, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?
            );
        """
        conn.execute(
            query,
            (
                profile_id, name, voice, language, target_market, audience_age_group,
                brand_colors, business_objective, words_to_avoid, preferred_cta_style,
                is_active, now_iso, now_iso
            )
        )

    return profile_id


def get_brand_profile(
    profile_id: str,
    db_path: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve brand profile by ID."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cursor = conn.execute("SELECT * FROM brand_profiles WHERE id = ?;", (str(profile_id).strip(),))
        row = cursor.fetchone()
        if row:
            return _deserialize_brand_profile_row(row)
    return None


def list_brand_profiles(db_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """List all saved brand profiles."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cursor = conn.execute("SELECT * FROM brand_profiles ORDER BY is_active DESC, name ASC;")
        rows = cursor.fetchall()
        return [_deserialize_brand_profile_row(r) for r in rows]


def ensure_default_brand_profiles(db_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """
    Ensure rich preset brand profiles exist in the database.
    Seeds Apex Athletics, Tech Career Accelerator, and SaaS Growth Studio if table is empty.
    """
    init_db(db_path)
    existing = list_brand_profiles(db_path)
    if existing:
        return existing

    presets = [
        {
            "name": "Apex Athletics",
            "voice": "High-performance, science-backed, direct & motivating",
            "language": "English",
            "target_market": "College athletes, fitness enthusiasts & gym-goers",
            "audience_age_group": "18-24",
            "brand_colors": "#00D1FF electric cyan, #7C5CFF deep violet",
            "business_objective": "Drive community engagement & training program signups",
            "words_to_avoid": "cheat code, easy, overnight, magic, effortless",
            "preferred_cta_style": "Direct challenge with actionable takeaway",
            "is_active": True,
        },
        {
            "name": "Tech Career Accelerator",
            "voice": "Authoritative, practical, empathetic, career-focused",
            "language": "English",
            "target_market": "College students, recent graduates & engineers preparing for placement drives & tech interviews",
            "audience_age_group": "18-24",
            "brand_colors": "#10B981 emerald green, #3B82F6 tech blue",
            "business_objective": "Educate students on resume building, coding rounds & placement drive success",
            "words_to_avoid": "guaranteed, secret sauce, trick, easy money",
            "preferred_cta_style": "Save this checklist for your next placement drive round",
            "is_active": False,
        },
        {
            "name": "SaaS Growth Studio",
            "voice": "Strategic, analytical, crisp, founder-first",
            "language": "English",
            "target_market": "B2B SaaS founders, indie hackers & tech leaders",
            "audience_age_group": "25-34",
            "brand_colors": "#7C5CFF electric violet, #00D1FF cyan",
            "business_objective": "Drive executive authority and newsletter subscriptions",
            "words_to_avoid": "synergy, groundbreaking, revolutionary, guru",
            "preferred_cta_style": "Read the complete breakdown in our weekly newsletter",
            "is_active": False,
        },
    ]

    for p in presets:
        create_brand_profile(p, db_path=db_path)

    return list_brand_profiles(db_path)


def get_active_brand_profile(db_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    """Retrieve the currently active brand profile."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cursor = conn.execute("SELECT * FROM brand_profiles WHERE is_active = 1 LIMIT 1;")
        row = cursor.fetchone()
        if row:
            return _deserialize_brand_profile_row(row)
    return None


def set_active_brand_profile(
    profile_id: str,
    db_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Set specified brand profile as active, clearing active status from all others."""
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute("UPDATE brand_profiles SET is_active = 0;")
        cursor = conn.execute("UPDATE brand_profiles SET is_active = 1 WHERE id = ?;", (str(profile_id).strip(),))
        return cursor.rowcount > 0


def update_brand_profile(
    profile_id: str,
    updates: Dict[str, Any],
    db_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Update an existing brand profile."""
    init_db(db_path)

    set_clauses: List[str] = []
    params: List[Any] = []

    for key, val in updates.items():
        if key not in BRAND_PROFILE_UPDATABLE_COLUMNS:
            continue
        if key == "is_active":
            val = 1 if val else 0
        set_clauses.append(f"{key} = ?")
        params.append(val)

    if not set_clauses:
        return False

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    set_clauses.append("updated_at = ?")
    params.append(now_iso)

    params.append(str(profile_id).strip())

    with get_db(db_path) as conn:
        if updates.get("is_active"):
            conn.execute("UPDATE brand_profiles SET is_active = 0;")
        query = f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ?;"
        cursor = conn.execute(query, tuple(params))
        return cursor.rowcount > 0


def delete_brand_profile(
    profile_id: str,
    db_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Delete a brand profile."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cursor = conn.execute("DELETE FROM brand_profiles WHERE id = ?;", (str(profile_id).strip(),))
        return cursor.rowcount > 0


# ============================================================
# APP SETTINGS & PREFERENCES
# ============================================================

def get_setting(
    key: str,
    default: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    """Retrieve an application setting value by key."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cursor = conn.execute("SELECT value FROM app_settings WHERE key = ?;", (str(key).strip(),))
        row = cursor.fetchone()
        return row["value"] if row else default


def set_setting(
    key: str,
    value: str,
    db_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Insert or update an application setting key-value pair."""
    init_db(db_path)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(db_path) as conn:
        conn.execute("""
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at;
        """, (str(key).strip(), str(value), now_iso))
        return True
