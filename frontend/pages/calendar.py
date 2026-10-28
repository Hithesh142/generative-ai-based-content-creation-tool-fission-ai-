"""
Fission AI - Editorial Calendar Page Module
Renders calendar metrics, view modes (Upcoming schedule vs 7-day week view),
reschedule/status popovers, RFC 5545 .ics / CSV exports, and interactive backlog scheduler.
"""

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st

from database.db import (
    ensure_default_brand_profiles,
    get_active_brand_profile,
    get_calendar_metrics,
    get_distinct_values,
    get_setting,
    init_db,
    list_calendar_items,
    list_items,
    update_item,
    update_schedule,
)
from frontend.components.header import render_header
from frontend.components.navigation import render_top_nav
from frontend.components.sidebar import render_sidebar
from frontend.styles import get_css
from services.content_generator import generate_content_ideas
from services.exporter import export_calendar_as_csv, export_calendar_as_ics


def render_calendar_page(show_nav: bool = False) -> None:
    """Render the Editorial Calendar view."""
    # Top navigation bar (when visited directly or as subpage)
    if show_nav:
        render_top_nav(active_page="calendar")

    st.markdown('<div class="section-title">📅 Content Editorial Calendar</div>', unsafe_allow_html=True)
    st.caption("Strategic planning and scheduling engine. (Planning and editorial tracking only — no automated posting claims).")

    today_str = datetime.date.today().isoformat()
    metrics = get_calendar_metrics(today_date=today_str)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Overdue Items", metrics["overdue"], delta="-overdue" if metrics["overdue"] > 0 else None, delta_color="inverse")
    with m2:
        st.metric("Upcoming Scheduled", metrics["upcoming"])
    with m3:
        st.metric("Published", metrics["published"])
    with m4:
        st.metric("Unscheduled Backlog", metrics["unscheduled"])
    with m5:
        st.metric("Total in Calendar", metrics["total_scheduled"])

    st.divider()

    # Filters & Layout Selection
    c_f1, c_f2, c_f3 = st.columns([3, 2, 3])
    with c_f1:
        cal_platform = st.selectbox("Filter Platform", ["All"] + get_distinct_values("platform"), index=0, key="cal_plat_filt")
    with c_f2:
        cal_status = st.selectbox("Filter Status", ["All", "Draft", "Planned", "Ready", "Published"], index=0, key="cal_stat_filt")
    with c_f3:
        cal_view_layout = st.radio("Calendar Layout", ["🗓️ Upcoming Schedule View", "📊 7-Day Week View"], horizontal=True, key="cal_layout_sel")

    scheduled_items = list_calendar_items(platform=cal_platform, status=cal_status)

    # Filter Alert Banner if items are filtered out
    if not scheduled_items and metrics["total_scheduled"] > 0:
        st.warning(
            f"⚠️ No scheduled items match your active filters (**Platform:** `{cal_platform}`, **Status:** `{cal_status}`). "
            f"You have **{metrics['total_scheduled']}** items scheduled in total."
        )
        if st.button("🔄 Reset Filters to 'All'", key="btn_reset_cal_filters", type="primary"):
            st.session_state["cal_plat_filt"] = "All"
            st.session_state["cal_stat_filt"] = "All"
            st.rerun()

    # Export Accordion
    with st.expander("📤 Export Calendar (.ICS & CSV)", expanded=False):
        st.markdown("Export your scheduled items to standard calendar software (Google Calendar, Apple Calendar, Outlook) or Excel:")
        e_c1, e_c2 = st.columns(2)
        with e_c1:
            ics_text = export_calendar_as_ics(scheduled_items)
            st.download_button(
                label="📅 Export as .ICS (Google/Apple/Outlook)",
                data=ics_text,
                file_name="fission_content_calendar.ics",
                mime="text/calendar",
                use_container_width=True,
                key="cal_ics_dl"
            )
        with e_c2:
            cal_csv = export_calendar_as_csv(scheduled_items)
            st.download_button(
                label="📊 Export Calendar as CSV",
                data=cal_csv,
                file_name="fission_content_calendar.csv",
                mime="text/csv",
                use_container_width=True,
                key="cal_csv_dl"
            )

    st.divider()

    # 1. UPCOMING SCHEDULE VIEW
    if cal_view_layout == "🗓️ Upcoming Schedule View":
        if not scheduled_items:
            st.info("📅 No scheduled content items found matching current filters. Schedule items from the backlog below or create ideas in the Studio!")
        else:
            for c_idx, c_item in enumerate(scheduled_items, start=1):
                item_date = c_item.get("scheduled_date")
                is_overdue = bool(item_date and item_date < today_str and c_item.get("status") != "Published")
                date_badge = f"🔴 OVERDUE: {item_date}" if is_overdue else f"📅 {item_date}"

                with st.container(border=True):
                    row1, row2 = st.columns([4, 1])
                    with row1:
                        st.subheader(f"{c_idx}. [{c_item.get('platform')}] {c_item.get('title')}")
                        st.caption(f"{date_badge} | Time: {c_item.get('scheduled_time') or '10:00'} | Format: {c_item.get('content_type')}")
                    with row2:
                        st.markdown(f"**Status:** `{c_item.get('status')}`")

                    if c_item.get("hook"):
                        st.markdown(f"**Hook:** {c_item['hook']}")
                    if c_item.get("caption"):
                        st.write(c_item["caption"][:180] + ("..." if len(c_item["caption"]) > 180 else ""))

                    act1, _ = st.columns([2, 6])
                    with act1:
                        with st.popover("⚙️ Edit Schedule & Status", use_container_width=True):
                            new_date = st.date_input("Date", value=datetime.date.fromisoformat(item_date) if item_date else datetime.date.today(), key=f"s_date_{c_item['id']}")
                            new_time = st.text_input("Time (HH:MM)", value=c_item.get("scheduled_time") or "10:00", key=f"s_time_{c_item['id']}")
                            status_options = ["Draft", "Planned", "Ready", "Published"]
                            cur_stat = c_item.get("status", "Draft")
                            stat_idx = status_options.index(cur_stat) if cur_stat in status_options else 0
                            new_status = st.selectbox("Status", status_options, index=stat_idx, key=f"s_stat_{c_item['id']}")
                            new_notes = st.text_area("Internal Notes", value=c_item.get("notes") or "", key=f"s_notes_{c_item['id']}")

                            if st.button("Save Changes", key=f"save_sched_{c_item['id']}", type="primary"):
                                update_item(
                                    c_item["id"],
                                    {
                                        "scheduled_date": new_date.isoformat(),
                                        "scheduled_time": new_time.strip(),
                                        "status": new_status,
                                        "notes": new_notes,
                                    }
                                )
                                st.toast("Schedule updated!", icon="📅")
                                st.rerun()

    # 2. 7-DAY WEEK VIEW (With Today Highlighting and Interactive Cards)
    elif cal_view_layout == "📊 7-Day Week View":
        base_today = datetime.date.today()
        week_days = [base_today + datetime.timedelta(days=i) for i in range(7)]
        day_cols = st.columns(7)

        for d_idx, day_obj in enumerate(week_days):
            day_iso = day_obj.isoformat()
            is_today = (day_obj == base_today)
            day_label = f"⭐ TODAY\n{day_obj.strftime('%a %b %d')}" if is_today else day_obj.strftime("%a %b %d")

            with day_cols[d_idx]:
                if is_today:
                    st.markdown(
                        f"""
                        <div style="background: rgba(124, 92, 255, 0.15); border: 2px solid #7C5CFF; border-radius: 8px; padding: 6px; text-align: center; margin-bottom: 8px;">
                            <span style="font-size: 11px; font-weight: 800; color: #00D1FF;">TODAY</span><br/>
                            <span style="font-weight: 700; font-size: 13px;">{day_obj.strftime('%a %b %d')}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"""
                        <div style="background: var(--fiss-surface-raised, #1B1B2A); border: 1px solid var(--fiss-border, #2A2A3D); border-radius: 8px; padding: 6px; text-align: center; margin-bottom: 8px;">
                            <span style="font-weight: 600; font-size: 13px; color: var(--fiss-text-muted, #A0A0B8);">{day_obj.strftime('%a %b %d')}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                day_posts = [it for it in scheduled_items if it.get("scheduled_date") == day_iso]
                if day_posts:
                    for dp in day_posts:
                        with st.container(border=True):
                            st.caption(f"**[{dp.get('platform')}]** • {dp.get('scheduled_time') or '10:00'}")
                            st.markdown(f"**{dp.get('title')[:22]}**")
                            st.caption(f"`{dp.get('status')}`")
                            with st.popover("⚙️ Edit", use_container_width=True):
                                e_time = st.text_input("Time", value=dp.get("scheduled_time") or "10:00", key=f"w_t_{dp['id']}")
                                e_stat = st.selectbox("Status", ["Draft", "Planned", "Ready", "Published"], index=["Draft", "Planned", "Ready", "Published"].index(dp.get("status", "Planned")), key=f"w_s_{dp['id']}")
                                if st.button("Save", key=f"w_save_{dp['id']}", type="primary", use_container_width=True):
                                    update_item(dp["id"], {"scheduled_time": e_time, "status": e_stat})
                                    st.toast("Item updated!", icon="✅")
                                    st.rerun()
                else:
                    st.markdown(
                        """
                        <div style="border: 1px dashed var(--fiss-border, #2A2A3D); border-radius: 8px; padding: 14px 4px; text-align: center; color: var(--fiss-text-muted, #A0A0B8); font-size: 12px;">
                            No posts
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    # 3. UNSCHEDULED BACKLOG SECTION (Interactive Quick-Schedule Cards)
    st.divider()
    unscheduled_items = list_items(limit=50)
    unscheduled_only = [it for it in unscheduled_items if not it.get("scheduled_date")]

    expand_backlog = (len(unscheduled_only) > 0 and len(scheduled_items) == 0)

    with st.expander(f"📥 Unscheduled Library Items ({len(unscheduled_only)} items in Backlog)", expanded=expand_backlog):
        if not unscheduled_only:
            st.caption("✅ All library items have been scheduled into the calendar!")
        else:
            st.markdown(f"Schedule your backlog items into specific editorial dates:")
            for u_item in unscheduled_only[:10]:
                with st.container(border=True):
                    r_c1, r_c2, r_c3, r_c4 = st.columns([4, 2, 2, 2])
                    with r_c1:
                        st.markdown(f"**[{u_item.get('platform', 'General')}] {u_item.get('title')}**")
                        if u_item.get("hook"):
                            st.caption(f"Hook: _{u_item['hook'][:70]}..._")
                    with r_c2:
                        assign_date = st.date_input("Assign Date", value=datetime.date.today(), key=f"quick_d_{u_item['id']}")
                    with r_c3:
                        assign_time = st.text_input("Time", value="10:00", key=f"quick_t_{u_item['id']}")
                    with r_c4:
                        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
                        if st.button("➕ Schedule", key=f"quick_btn_{u_item['id']}", type="primary", use_container_width=True):
                            update_schedule(u_item["id"], scheduled_date=assign_date.isoformat(), scheduled_time=assign_time.strip())
                            update_item(u_item["id"], {"status": "Planned"})
                            st.session_state["cal_plat_filt"] = "All"
                            st.session_state["cal_stat_filt"] = "All"
                            st.toast(f"✅ Scheduled '{u_item.get('title')}' for {assign_date.isoformat()}!", icon="📅")
                            st.rerun()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    st.set_page_config(page_title="Fission AI - Editorial Calendar", page_icon="📅", layout="wide")

    init_db()
    ensure_default_brand_profiles()
    theme_mode = st.session_state.get("theme", get_setting("theme", "dark"))
    st.markdown(get_css(theme=theme_mode), unsafe_allow_html=True)
    active_brand = get_active_brand_profile()
    render_header(active_brand=active_brand)

    # Render sidebar control panel on calendar page too!
    sidebar_inputs = render_sidebar()

    if sidebar_inputs.get("generate_clicked"):
        topic_val = sidebar_inputs.get("topic", "").strip()
        if topic_val:
            try:
                import uuid
                with st.spinner(f"Writing hooks, angles, and visual concepts for '{topic_val}' via Groq..."):
                    keywords_raw = sidebar_inputs.get("keywords")
                    parsed_keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else None

                    gen_result = generate_content_ideas(
                        topic=topic_val,
                        platform=sidebar_inputs.get("platform", "Instagram"),
                        audience=sidebar_inputs.get("audience", ""),
                        tone=sidebar_inputs.get("tone", "Professional"),
                        content_type=sidebar_inputs.get("content_type", "Post"),
                        number_of_ideas=sidebar_inputs.get("number_of_ideas", 5),
                        keywords=parsed_keywords,
                        campaign_objective=sidebar_inputs.get("campaign_objective"),
                        brand_profile=sidebar_inputs.get("active_brand"),
                    )

                    st.session_state.generation_id = uuid.uuid4().hex[:8]
                    st.session_state.generated_result = gen_result
                    st.session_state.generated_topic = topic_val
                    st.session_state.generated_platform = sidebar_inputs.get("platform", "Instagram")
                    st.session_state.generated_audience = sidebar_inputs.get("audience", "")
                    st.toast(f"✅ Generated {len(gen_result.get('ideas', []))} content concepts for '{topic_val}'!", icon="✨")
            except Exception as e:
                st.error(f"❌ Strategy generation error: {str(e)}")

    render_calendar_page(show_nav=True)
