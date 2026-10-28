"""
Fission AI - Studio Metric Strip Component
Displays 4 high-level telemetry tiles: Ideas Generated, Images Generated, Scheduled This Week, Drafts.
"""

import datetime
from typing import Optional
import streamlit as st
from database.db import count_items, list_calendar_items


def render_studio_metrics(session_ideas_count: int = 0, session_images_count: int = 0) -> None:
    """Render the 4-tile studio dashboard summary strip."""
    # Compute calendar schedule count for this week
    today = datetime.date.today()
    week_start = (today - datetime.timedelta(days=today.weekday())).isoformat()
    week_end = (today + datetime.timedelta(days=6 - today.weekday())).isoformat()

    try:
        week_items = list_calendar_items(start_date=week_start, end_date=week_end)
        scheduled_this_week = len(week_items)
        drafts_count = count_items(status="Draft")
    except Exception:
        scheduled_this_week = 0
        drafts_count = 0

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric(
            label="💡 Ideas in Studio",
            value=session_ideas_count,
            help="Total ideas active in current strategy session."
        )

    with m2:
        st.metric(
            label="🖼️ Visuals Rendered",
            value=session_images_count,
            help="Images generated in active session state cache."
        )

    with m3:
        st.metric(
            label="📅 Scheduled This Week",
            value=scheduled_this_week,
            help="Editorial items scheduled for the current week (Mon-Sun)."
        )

    with m4:
        st.metric(
            label="📝 Drafts in Backlog",
            value=drafts_count,
            help="Total items saved in library with Draft status."
        )
