"""
Fission AI - Studio Page Module
Renders Content Plan generator (7/30-day), telemetry metric strip,
responsive 2-column idea card grid, and recent generations strip.
"""

import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import streamlit as st

from database.db import create_item, get_recent_images
from frontend.components.empty_state import render_empty_state
from frontend.components.idea_card import render_idea_card
from frontend.components.metrics import render_studio_metrics
from frontend.components.navigation import render_top_nav
from services.ai_tools import generate_content_plan


def render_studio_page(sidebar_inputs: Dict[str, Any], show_nav: bool = False) -> None:
    """Render the primary Content Studio view."""
    if show_nav:
        render_top_nav(active_page="studio")

    active_brand = sidebar_inputs.get("active_brand")
    image_engine = sidebar_inputs.get("image_engine", "Cloudflare Workers AI")

    # 1. CONTENT PLAN GENERATOR (7-Day / 30-Day Campaign Expander)
    with st.expander("📅 Strategic Content Plan Generator (7-Day & 30-Day Campaign)", expanded=False):
        st.markdown("Generate a multi-day editorial campaign with scheduled format rotation, hooks, and visual concepts.")
        p_c1, p_c2, p_c3, p_c4 = st.columns([3, 2, 2, 2])
        with p_c1:
            plan_topic = st.text_input("Campaign Theme / Topic", placeholder="e.g. AI Automation for Small Business", key="cp_topic")
        with p_c2:
            plan_duration = st.selectbox("Campaign Length", [7, 30], format_func=lambda x: f"{x}-Day Roadmap", key="cp_dur")
        with p_c3:
            plan_start_date = st.date_input("Start Date", value=datetime.date.today(), key="cp_start")
        with p_c4:
            plan_platform = st.selectbox("Platform Scope", ["Multi-Platform", "Instagram", "LinkedIn", "Twitter / X", "TikTok"], key="cp_plat")

        if st.button("🚀 Generate Strategic Content Plan", type="primary", key="btn_gen_plan"):
            if not plan_topic.strip():
                st.warning("Please provide a campaign theme.")
            else:
                try:
                    with st.spinner(f"Building {plan_duration}-day structured content plan with Groq..."):
                        plan_res = generate_content_plan(
                            topic=plan_topic,
                            duration_days=plan_duration,
                            platform=plan_platform,
                            start_date=plan_start_date.isoformat(),
                            brand_profile=active_brand,
                        )
                        st.session_state.active_content_plan = plan_res
                        st.session_state.active_plan_start_date = plan_start_date.isoformat()
                        st.toast(f"Generated {plan_duration}-day editorial plan!", icon="📅")
                except Exception as p_err:
                    st.error(f"Error generating plan: {p_err}")

        # Display Plan & 1-Click Save to Library & Calendar
        if "active_content_plan" in st.session_state and st.session_state.active_content_plan:
            active_plan = st.session_state.active_content_plan
            st.markdown(f"**Strategy Overview:** _{active_plan.strategy_summary}_")

            if st.button(f"💾 Save All {len(active_plan.plan)} Items into Library & Calendar (1-Click)", key="save_plan_all_btn", type="primary"):
                saved_count = 0
                base_dt = datetime.date.fromisoformat(st.session_state.get("active_plan_start_date", datetime.date.today().isoformat()))
                for item in active_plan.plan:
                    scheduled_dt = (base_dt + datetime.timedelta(days=item.day - 1)).isoformat()
                    item_dict = {
                        "topic": active_plan.topic,
                        "title": item.title,
                        "platform": item.platform,
                        "content_type": item.content_type,
                        "hook": item.hook,
                        "caption": item.caption,
                        "cta": item.cta,
                        "hashtags": item.hashtags,
                        "visual_concept": item.visual_concept,
                        "image_prompt": item.image_prompt,
                        "scheduled_date": scheduled_dt,
                        "status": "Planned",
                        "notes": f"Generated as Day {item.day} of {active_plan.topic} campaign.",
                    }
                    create_item(item_dict)
                    saved_count += 1
                st.toast(f"✅ Successfully saved {saved_count} items to Library and Calendar!", icon="📅")
                st.rerun()

            plan_preview_rows = []
            for item in active_plan.plan:
                plan_preview_rows.append({
                    "Day": f"Day {item.day}",
                    "Format": item.content_type,
                    "Platform": item.platform,
                    "Headline / Title": item.title,
                    "Hook Snippet": item.hook[:60] + "...",
                })
            st.dataframe(plan_preview_rows, use_container_width=True)

    st.divider()

    # 2. STUDIO TELEMETRY METRIC STRIP
    ideas_count = 0
    if st.session_state.get("generated_result") and "ideas" in st.session_state.generated_result:
        ideas_count = len(st.session_state.generated_result["ideas"])
    rendered_images_count = sum(1 for v in st.session_state.get("image_cache", {}).values() if getattr(v, "is_success", False))
    render_studio_metrics(session_ideas_count=ideas_count, session_images_count=rendered_images_count)

    st.divider()

    # 3. IDEA CARDS RESPONSIVE GRID (2 columns)
    if not st.session_state.get("generated_result"):
        render_empty_state(
            title="Studio Workspace Ready",
            description="Configure your topic and target audience in the left Studio Control panel, then generate your multi-angle content strategy.",
            button_label="👈 Set Topic in Sidebar"
        )
    else:
        result = st.session_state.generated_result
        display_topic = st.session_state.get("generated_topic", sidebar_inputs.get("topic", ""))
        display_platform = st.session_state.get("generated_platform", sidebar_inputs.get("platform", ""))
        display_audience = st.session_state.get("generated_audience", sidebar_inputs.get("audience", ""))
        ideas = result.get("ideas", [])
        gen_id = st.session_state.get("generation_id", "default")

        # Top Session Context Bar
        st.markdown(
            f"""
            <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 16px; flex-wrap: wrap;">
                <span class="fiss-chip" style="font-weight: 600; font-size: 14px;">🎯 Topic: {display_topic}</span>
                <span class="fiss-chip">📱 Platform: {display_platform}</span>
                <span class="fiss-chip">👥 Audience: {display_audience or 'General'}</span>
                <span class="fiss-chip">💡 Ideas: {len(ideas)}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        col_left, col_right = st.columns(2)

        for index, idea in enumerate(ideas, start=1):
            target_col = col_left if index % 2 == 1 else col_right
            with target_col:
                render_idea_card(
                    index=index,
                    idea=idea,
                    gen_id=gen_id,
                    topic=display_topic,
                    platform=display_platform,
                    audience=display_audience,
                    active_brand=active_brand,
                    image_engine=image_engine,
                )

    # 4. RECENT GENERATIONS STRIP
    st.divider()
    st.markdown("### 🕒 Recent Visual Generations")
    recent_images = get_recent_images(limit=6)
    if recent_images:
        r_cols = st.columns(min(len(recent_images), 6))
        for r_idx, r_item in enumerate(recent_images[:6]):
            with r_cols[r_idx]:
                if Path(r_item["image_path"]).exists():
                    st.image(r_item["image_path"], use_container_width=True)
                    st.caption(f"**{r_item['title'][:18]}**")
    else:
        st.caption("No previous visual generations saved in library yet.")


if __name__ == "__main__":
    import sys
    import uuid
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    st.set_page_config(page_title="Fission AI - Content Studio", page_icon="🚀", layout="wide")

    from database.db import ensure_default_brand_profiles, get_active_brand_profile, get_setting, init_db
    from frontend.components.header import render_header
    from frontend.components.sidebar import render_sidebar
    from frontend.styles import get_css
    from services.content_generator import generate_content_ideas

    init_db()
    ensure_default_brand_profiles()
    theme_mode = st.session_state.get("theme", get_setting("theme", "dark"))
    st.markdown(get_css(theme=theme_mode), unsafe_allow_html=True)
    active_brand = get_active_brand_profile()
    render_header(active_brand=active_brand)
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

    render_studio_page(sidebar_inputs=sidebar_inputs, show_nav=True)

