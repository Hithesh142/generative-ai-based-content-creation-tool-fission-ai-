"""
Fission AI - Content Export Service
Decoupled exporter providing safe, multi-format exports:
- Caption as TXT
- Image as PNG / JPEG
- Items as CSV (UTF-8 with BOM for direct Excel compatibility)
- Campaign Plan as JSON
- Selected / All Items as a self-contained ZIP archive (captions, images, CSV, JSON)
All file names are safely slugified to prevent directory traversal and OS naming collisions.
"""

import codecs
import csv
import datetime
import io
import json
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image

# Forbidden characters in filenames across Windows and POSIX systems
FORBIDDEN_FILENAME_CHARS = re.compile(r'[\\/*?:"<>|]')


def slugify_filename(text: str, max_length: int = 50, default: str = "export") -> str:
    """
    Sanitize text into a safe, valid cross-platform filename.
    Guarantees:
    - Zero path traversal characters ('..', '/', '\\')
    - Stripping of Windows/POSIX reserved symbols
    - Trimmed whitespace and trailing dots
    - Bounded length
    """
    if not text or not str(text).strip():
        return default

    # Remove null bytes and control chars
    clean = re.sub(r"[\x00-\x1f\x7f]", "", str(text))

    # Strip path traversal indicators
    clean = clean.replace("..", "").replace("/", "_").replace("\\", "_")

    # Keep only alphanumeric, hyphens, and underscores for clean slugs
    clean = re.sub(r"[^A-Za-z0-9_\-\s]", "", clean)

    # Normalize whitespace, underscores, and hyphens
    clean = re.sub(r"[\s_]+", "_", clean).strip(" ._-")

    if not clean:
        return default

    # Bound length
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip(" ._-")

    return clean or default


def export_caption_as_txt(item: Dict[str, Any]) -> str:
    """
    Format a content item into a structured plain text document.
    """
    title = item.get("title", "Untitled")
    platform = item.get("platform", "General")
    topic = item.get("topic", "")
    target_audience = item.get("target_audience", "")
    content_type = item.get("content_type", "")
    status = item.get("status", "Draft")
    hook = item.get("hook", "")
    caption = item.get("caption", "")
    cta = item.get("cta", "")
    notes = item.get("notes", "")

    raw_hashtags = item.get("hashtags", [])
    if isinstance(raw_hashtags, list):
        hashtags_str = " ".join(raw_hashtags)
    else:
        hashtags_str = str(raw_hashtags or "")

    visual_concept = item.get("visual_concept", "")
    image_prompt = item.get("image_prompt", "")

    lines = [
        f"TITLE: {title}",
        f"PLATFORM: {platform}",
        f"TOPIC: {topic}",
        f"CONTENT TYPE: {content_type}",
        f"TARGET AUDIENCE: {target_audience}",
        f"STATUS: {status}",
        "",
        "=" * 60,
        "HOOK / HEADLINE",
        "=" * 60,
        hook or "(None)",
        "",
        "=" * 60,
        "CAPTION / POST BODY",
        "=" * 60,
        caption or "(None)",
        "",
        "=" * 60,
        "CALL TO ACTION (CTA)",
        "=" * 60,
        cta or "(None)",
        "",
        "=" * 60,
        "HASHTAGS",
        "=" * 60,
        hashtags_str or "(None)",
        "",
        "=" * 60,
        "VISUAL CONCEPT & IMAGE PROMPT",
        "=" * 60,
        f"Concept: {visual_concept or '(None)'}",
        f"Prompt:  {image_prompt or '(None)'}",
    ]

    if notes:
        lines.extend([
            "",
            "=" * 60,
            "NOTES",
            "=" * 60,
            notes,
        ])

    return "\n".join(lines)


def export_image_bytes(
    image_path: Union[str, Path],
    target_format: str = "PNG",
) -> bytes:
    """
    Read an image file and export it as PNG or JPEG bytes.
    Raises FileNotFoundError if image does not exist.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file does not exist: {image_path}")

    fmt = target_format.upper().strip()
    if fmt not in ("PNG", "JPEG", "JPG"):
        fmt = "PNG"

    with Image.open(path) as img:
        output = io.BytesIO()
        if fmt in ("JPEG", "JPG"):
            # JPEG requires RGB mode (cannot save RGBA)
            rgb_img = img.convert("RGB")
            rgb_img.save(output, format="JPEG", quality=95)
        else:
            img.save(output, format="PNG")
        return output.getvalue()


def export_items_as_csv(items: List[Dict[str, Any]]) -> bytes:
    """
    Export a list of content items to CSV bytes encoded with UTF-8 BOM (utf-8-sig).
    The UTF-8 BOM guarantees that Microsoft Excel on Windows renders special
    characters and emojis without corruption.
    """
    fields = [
        "id",
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
        "created_at",
        "updated_at",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()

    for item in items:
        row = dict(item)

        # Format hashtags
        ht = row.get("hashtags")
        if isinstance(ht, list):
            row["hashtags"] = " ".join(ht)
        elif ht is None:
            row["hashtags"] = ""

        # Format tags
        tg = row.get("tags")
        if isinstance(tg, list):
            row["tags"] = ", ".join(tg)
        elif tg is None:
            row["tags"] = ""

        writer.writerow(row)

    # Encode with UTF-8 BOM for Excel compatibility
    csv_str = output.getvalue()
    return codecs.BOM_UTF8 + csv_str.encode("utf-8")


def export_items_as_json(items: Union[List[Dict[str, Any]], Dict[str, Any]]) -> str:
    """
    Export content item(s) to a formatted JSON string.
    """
    return json.dumps(items, indent=2, ensure_ascii=False)


def export_items_as_zip(
    items: List[Dict[str, Any]],
    zip_title: Optional[str] = None,
) -> bytes:
    """
    Package content items into a ZIP archive containing:
    - content_summary.csv: Spreadsheet of all items with UTF-8 BOM.
    - campaign_plan.json: Full structured metadata.
    - Folders per item containing:
        - caption.txt: Formatted text export.
        - image.png: Copied generated visual (if present).
    Returns the ZIP archive as in-memory bytes.
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Add Summary CSV
        csv_bytes = export_items_as_csv(items)
        zf.writestr("content_summary.csv", csv_bytes)

        # 2. Add JSON Metadata
        json_str = export_items_as_json(items)
        zf.writestr("campaign_plan.json", json_str.encode("utf-8"))

        # 3. Add Item Folders with TXT captions and images
        for index, item in enumerate(items, start=1):
            title_slug = slugify_filename(item.get("title") or item.get("id") or f"item_{index}")
            folder_name = f"{index:02d}_{title_slug}"

            # Caption TXT
            caption_text = export_caption_as_txt(item)
            zf.writestr(f"{folder_name}/caption.txt", caption_text.encode("utf-8"))

            # Image
            img_path_str = item.get("image_path")
            if img_path_str:
                path = Path(img_path_str)
                if path.exists() and path.is_file():
                    try:
                        img_bytes = path.read_bytes()
                        img_suffix = path.suffix or ".png"
                        zf.writestr(f"{folder_name}/image{img_suffix}", img_bytes)
                    except Exception:
                        pass

    return zip_buffer.getvalue()


def _escape_ics_text(text: str) -> str:
    """Escape text according to RFC 5545 iCalendar specification."""
    if not text:
        return ""
    clean = (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )
    return clean


def export_calendar_as_ics(
    items: List[Dict[str, Any]],
    calendar_name: str = "Fission AI Content Calendar",
) -> str:
    """
    Export scheduled content items to an RFC 5545 compliant iCalendar (.ics) string.
    Importable into Google Calendar, Apple Calendar, and Microsoft Outlook.
    """
    now_dt = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Fission AI//Content Calendar 1.0//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_ics_text(calendar_name)}",
        "X-WR-TIMEZONE:UTC",
    ]

    for item in items:
        sched_date = item.get("scheduled_date")
        if not sched_date:
            continue

        date_parts = str(sched_date).strip().split("-")
        if len(date_parts) != 3:
            continue

        date_str = "".join(date_parts)
        sched_time = item.get("scheduled_time")

        item_uid = item.get("id") or uuid.uuid4().hex
        uid = f"{item_uid}@fission.ai"
        summary = _escape_ics_text(f"[{item.get('platform', 'Social')}] {item.get('title', 'Content Post')}")

        desc_parts = [
            f"Platform: {item.get('platform', '')}",
            f"Format: {item.get('content_type', '')}",
            f"Status: {item.get('status', 'Draft')}",
            "",
            f"Hook: {item.get('hook', '')}",
            "",
            f"Caption: {item.get('caption', '')}",
            "",
            f"CTA: {item.get('cta', '')}",
        ]
        description = _escape_ics_text("\n".join(desc_parts))

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}")
        lines.append(f"DTSTAMP:{now_dt}")

        if sched_time and ":" in str(sched_time):
            time_parts = str(sched_time).strip().split(":")
            hh = time_parts[0].zfill(2)
            mm = time_parts[1].zfill(2)
            dt_start = f"{date_str}T{hh}{mm}00Z"
            end_hh = str((int(hh) + 1) % 24).zfill(2)
            dt_end = f"{date_str}T{end_hh}{mm}00Z"
            lines.append(f"DTSTART:{dt_start}")
            lines.append(f"DTEND:{dt_end}")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{date_str}")

        lines.append(f"SUMMARY:{summary}")
        lines.append(f"DESCRIPTION:{description}")
        lines.append(f"STATUS:{'CONFIRMED' if item.get('status') in ('Ready', 'Published') else 'TENTATIVE'}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def export_calendar_as_csv(items: List[Dict[str, Any]]) -> bytes:
    """Export scheduled content calendar items to CSV bytes with UTF-8 BOM."""
    fields = [
        "scheduled_date",
        "scheduled_time",
        "platform",
        "status",
        "title",
        "content_type",
        "target_audience",
        "hook",
        "caption",
        "cta",
        "hashtags",
        "id",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()

    for item in items:
        row = dict(item)
        ht = row.get("hashtags")
        if isinstance(ht, list):
            row["hashtags"] = " ".join(ht)
        writer.writerow(row)

    return codecs.BOM_UTF8 + output.getvalue().encode("utf-8")

