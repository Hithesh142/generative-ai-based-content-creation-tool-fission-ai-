"""
Fission AI - Library Page Module
Renders saved items list, search & filters, visual gallery view,
bulk exports (CSV with BOM, JSON, ZIP bundle), item edit/delete.
"""

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st

from database.db import (
    count_items,
    delete_item,
    get_distinct_values,
    list_items,
    update_item,
)
from frontend.components.navigation import render_top_nav
from services.exporter import (
    export_caption_as_txt,
    export_items_as_csv,
    export_items_as_json,
    export_items_as_zip,
    slugify_filename,
)


def render_library_page(show_nav: bool = False) -> None:
    """Render the Content Library view."""
    if show_nav:
        render_top_nav(active_page="library")

    st.markdown('<div class="section-title">📚 Content Library & Knowledge Base</div>', unsafe_allow_html=True)
    st.caption("Central SQLite-backed storage for all saved content items, generated visuals, and export bundles.")

    # Library Summary Metrics
    total_count = count_items()
    draft_count = count_items(status="Draft")
    planned_count = count_items(status="Planned")
    ready_count = count_items(status="Ready")
    published_count = count_items(status="Published")

    met_col1, met_col2, met_col3, met_col4, met_col5 = st.columns(5)
    with met_col1:
        st.metric("Total Items", total_count)
    with met_col2:
        st.metric("Draft", draft_count)
    with met_col3:
        st.metric("Planned", planned_count)
    with met_col4:
        st.metric("Ready", ready_count)
    with met_col5:
        st.metric("Published", published_count)

    st.divider()

    # Search & Filters
    f_col1, f_col2, f_col3, f_col4 = st.columns([3, 2, 2, 2])
    with f_col1:
        lib_search = st.text_input("Search Content", placeholder="Search topic, title, hook, or caption...", key="lib_search_input")
    with f_col2:
        lib_platform = st.selectbox("Platform", ["All"] + get_distinct_values("platform"), index=0, key="lib_platform_filter")
    with f_col3:
        lib_status = st.selectbox("Status", ["All", "Draft", "Planned", "Ready", "Published"], index=0, key="lib_status_filter")
    with f_col4:
        lib_sort = st.selectbox("Sort Order", ["Newest First", "Oldest First", "Title A-Z", "Scheduled Date"], index=0, key="lib_sort_select")

    sort_column_map = {
        "Newest First": ("created_at", "DESC"),
        "Oldest First": ("created_at", "ASC"),
        "Title A-Z": ("title", "ASC"),
        "Scheduled Date": ("scheduled_date", "ASC"),
    }
    sort_col, sort_ord = sort_column_map.get(lib_sort, ("created_at", "DESC"))

    filtered_items = list_items(
        search=lib_search,
        platform=lib_platform,
        status=lib_status,
        sort_by=sort_col,
        sort_order=sort_ord,
        limit=100
    )

    # Bulk Export Accordion
    with st.expander("📦 Export Library Bundle (Selected / Filtered)", expanded=False):
        st.markdown(f"Export all **{len(filtered_items)}** currently filtered content items:")
        exp_col1, exp_col2, exp_col3 = st.columns(3)
        if filtered_items:
            with exp_col1:
                csv_bytes = export_items_as_csv(filtered_items)
                st.download_button(
                    label="📊 Export as CSV (Excel BOM)",
                    data=csv_bytes,
                    file_name="fission_content_library.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="bulk_csv_dl"
                )
            with exp_col2:
                json_data = export_items_as_json(filtered_items)
                st.download_button(
                    label="📄 Export as JSON",
                    data=json_data,
                    file_name="fission_content_library.json",
                    mime="application/json",
                    use_container_width=True,
                    key="bulk_json_dl"
                )
            with exp_col3:
                zip_bytes = export_items_as_zip(filtered_items)
                st.download_button(
                    label="📦 Export as ZIP (Images + Text)",
                    data=zip_bytes,
                    file_name="fission_library_bundle.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="bulk_zip_dl"
                )

    st.divider()

    view_mode = st.radio("Display Mode", ["📋 Content Cards View", "🖼️ Visual Gallery View"], horizontal=True, key="lib_view_mode")

    if not filtered_items:
        st.info("🔍 No content items found matching your filters. Create and save ideas in the Content Studio to populate your library!")
    else:
        if view_mode == "📋 Content Cards View":
            for lib_idx, item in enumerate(filtered_items, start=1):
                item_id = item["id"]
                item_title = item.get("title", "Untitled Concept")
                item_status = item.get("status", "Draft")
                item_platform = item.get("platform", "General")
                item_type = item.get("content_type", "Post")
                item_hook = item.get("hook", "")
                item_caption = item.get("caption", "")
                item_cta = item.get("cta", "")
                item_hashtags = item.get("hashtags", [])
                item_image_path = item.get("image_path")
                item_sched_date = item.get("scheduled_date")
                item_sched_time = item.get("scheduled_time")

                with st.container(border=True):
                    h_col1, h_col2 = st.columns([4, 1])
                    with h_col1:
                        st.subheader(f"{lib_idx}. {item_title}")
                        sched_badge = f"📅 Scheduled: {item_sched_date} ({item_sched_time or 'All Day'})" if item_sched_date else "⚪ Unscheduled"
                        st.caption(f"**Topic:** {item.get('topic', 'General')} | **Platform:** {item_platform} | **Format:** {item_type} | {sched_badge}")
                    with h_col2:
                        st.markdown(f"**Status:** `{item_status}`")

                    c_left, c_right = st.columns([1, 2] if (item_image_path and Path(item_image_path).exists()) else [1, 20])

                    if item_image_path and Path(item_image_path).exists():
                        with c_left:
                            st.image(item_image_path, use_container_width=True)
                            with open(item_image_path, "rb") as f_img:
                                st.download_button("⬇️ Image (PNG)", data=f_img, file_name=Path(item_image_path).name, mime="image/png", key=f"lib_img_dl_{item_id}", use_container_width=True)

                    with c_right:
                        if item_hook:
                            st.markdown(f"**🎯 Hook:** {item_hook}")
                        if item_caption:
                            st.markdown("**✍️ Caption:**")
                            st.write(item_caption)
                        if item_cta:
                            st.markdown(f"**📢 CTA:** {item_cta}")

                        st.caption("📋 Quick Copy:")
                        cp_col1, cp_col2 = st.columns(2)
                        with cp_col1:
                            st.code(item_caption, language=None)
                        with cp_col2:
                            ht_str = " ".join(item_hashtags) if isinstance(item_hashtags, list) else str(item_hashtags or "")
                            st.code(ht_str, language=None)

                    # Action Toolbar
                    act_col1, act_col2, act_col3, act_col4 = st.columns([2, 2, 2, 2])
                    with act_col1:
                        if st.button("🚀 Reopen in Studio", key=f"reopen_{item_id}", use_container_width=True):
                            st.session_state.generated_topic = item.get("topic", "")
                            st.session_state.generated_platform = item.get("platform", "")
                            st.session_state.generated_audience = item.get("target_audience", "")
                            st.session_state.generated_result = {
                                "ideas": [{
                                    "title": item_title,
                                    "content_type": item_type,
                                    "target_audience": item.get("target_audience", ""),
                                    "duration_estimate": "N/A",
                                    "hook": item_hook,
                                    "caption": item_caption,
                                    "call_to_action": item_cta,
                                    "hashtags": item_hashtags,
                                    "visual_concept": item.get("visual_concept", ""),
                                    "image_prompt": item.get("image_prompt", ""),
                                }]
                            }
                            st.toast("Item loaded into Studio! Switch to the Studio tab.", icon="🚀")

                    with act_col2:
                        caption_txt = export_caption_as_txt(item)
                        item_slug = slugify_filename(item_title)
                        st.download_button("📄 Export TXT", data=caption_txt, file_name=f"{item_slug}_caption.txt", mime="text/plain", key=f"dl_txt_{item_id}", use_container_width=True)

                    with act_col3:
                        with st.popover("📅 Edit / Schedule", use_container_width=True):
                            e_title = st.text_input("Title", value=item_title, key=f"e_title_{item_id}")
                            e_status = st.selectbox("Status", ["Draft", "Planned", "Ready", "Published"], index=["Draft", "Planned", "Ready", "Published"].index(item_status) if item_status in ["Draft", "Planned", "Ready", "Published"] else 0, key=f"e_status_{item_id}")
                            e_date = st.date_input("Scheduled Date", value=datetime.date.fromisoformat(item_sched_date) if item_sched_date else datetime.date.today(), key=f"e_date_{item_id}")
                            e_time = st.text_input("Scheduled Time", value=item_sched_time or "10:00", key=f"e_time_{item_id}")
                            e_caption = st.text_area("Caption", value=item_caption, key=f"e_caption_{item_id}")

                            if st.button("Save Changes", key=f"e_save_{item_id}", type="primary", use_container_width=True):
                                update_item(
                                    item_id,
                                    {
                                        "title": e_title,
                                        "status": e_status,
                                        "scheduled_date": e_date.isoformat(),
                                        "scheduled_time": e_time.strip(),
                                        "caption": e_caption,
                                    }
                                )
                                st.toast("Item updated successfully!", icon="✅")
                                st.rerun()

                    with act_col4:
                        with st.popover("🗑️ Delete", use_container_width=True):
                            st.warning(f"Delete '{item_title}' permanently?")
                            if st.button("Confirm Delete", key=f"confirm_del_{item_id}", type="primary", use_container_width=True):
                                delete_item(item_id)
                                st.toast("Item deleted from library.", icon="🗑️")
                                st.rerun()

        elif view_mode == "🖼️ Visual Gallery View":
            gallery_items = [it for it in filtered_items if it.get("image_path") and Path(it["image_path"]).exists()]
            if not gallery_items:
                st.info("No saved images found in the filtered library items.")
            else:
                num_cols = 3
                g_cols = st.columns(num_cols)
                for g_idx, g_item in enumerate(gallery_items):
                    with g_cols[g_idx % num_cols]:
                        with st.container(border=True):
                            st.image(g_item["image_path"], use_container_width=True)
                            st.subheader(g_item.get("title", "Untitled"))
                            st.caption(f"**Topic:** {g_item.get('topic')} | **Status:** `{g_item.get('status')}`")


if __name__ == "__main__":
    import sys
    import uuid
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    st.set_page_config(page_title="Fission AI - Content Library", page_icon="📚", layout="wide")

    from database.db import ensure_default_brand_profiles, get_active_brand_profile, get_setting, init_db
    from frontend.components.header import render_header
    from frontend.components.sidebar import render_sidebar
    from frontend.styles import get_css
    from services.content_generator import generate_content_ideas

    init_db()
    ensure_default_brand_profiles()
    theme_mode = st.session_state.get("theme", get_setting("theme", "dark"))
    st.markdown(get_css(theme=theme_mode), unsafe_allow_html=True)
    render_header(active_brand=get_active_brand_profile())

    sidebar_inputs = render_sidebar()

    if sidebar_inputs.get("generate_clicked"):
        topic_val = sidebar_inputs.get("topic", "").strip()
        if topic_val:
            try:
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

    render_library_page(show_nav=True)

