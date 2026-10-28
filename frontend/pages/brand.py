"""
Fission AI - Brand Profiles Page Module
Renders brand profiles list, active switcher, create/edit form, and delete actions.
"""

from typing import Any, Dict, List, Optional
import streamlit as st

from database.db import (
    create_brand_profile,
    delete_brand_profile,
    get_active_brand_profile,
    list_brand_profiles,
    set_active_brand_profile,
)
from frontend.components.navigation import render_top_nav


def render_brand_page(show_nav: bool = False) -> None:
    """Render the Brand Profiles management view."""
    if show_nav:
        render_top_nav(active_page="brand")

    st.markdown('<div class="section-title">🎨 Brand Identity & Style Profiles</div>', unsafe_allow_html=True)
    st.caption("Define your unique brand voice, color palette, target demographics, and forbidden words. The active profile automatically steers Groq generation and visual styling.")

    all_profiles = list_brand_profiles()
    active_brand = get_active_brand_profile()

    # Active profile indicator
    if active_brand:
        st.success(f"🟢 **Active Profile:** {active_brand['name']} | Voice: _{active_brand.get('voice', 'Standard')}_ | Language: {active_brand.get('language', 'English')}")
    else:
        st.info("⚪ No brand profile is currently active. The studio uses standard default prompts.")

    st.divider()

    # Create New Brand Profile Expander
    with st.expander("➕ Create New Brand Profile", expanded=len(all_profiles) == 0):
        np_col1, np_col2 = st.columns(2)
        with np_col1:
            bp_name = st.text_input("Brand Name *", placeholder="e.g. Apex Athletics", help="Company or creator brand name", key="np_name")
            bp_voice = st.text_input("Brand Voice & Tone", placeholder="e.g. High-performance, science-backed, direct", help="Key adjectives describing tone", key="np_voice")
            bp_language = st.selectbox("Language", ["English", "Spanish", "French", "German", "Hindi", "Portuguese", "Japanese"], key="np_lang")
            bp_target = st.text_input("Target Market / Niche", placeholder="e.g. B2B SaaS Founders, Fitness Enthusiasts", key="np_target")
            bp_age = st.selectbox("Target Age Group", ["All Ages", "18-24", "25-34", "35-50", "50+"], key="np_age")
        with np_col2:
            bp_colors = st.text_input("Brand Visual Palette", placeholder="e.g. #00B4D8 electric cyan, #03045E navy", help="Used to guide image color grading", key="np_colors")
            bp_obj = st.text_input("Primary Business Objective", placeholder="e.g. Drive newsletter signups, build executive authority", key="np_obj")
            bp_avoid = st.text_area("Words to Avoid (Negative Keywords)", placeholder="e.g. synergy, robust, groundbreaking, cheat code, easy", help="Comma-separated words Groq is strictly forbidden from using", key="np_avoid")
            bp_cta = st.text_input("Preferred CTA Style", placeholder="e.g. Direct question with action link", key="np_cta")
            bp_active = st.checkbox("Set as active profile immediately", value=True, key="np_active")

        submitted = st.button("💾 Save Brand Profile", type="primary", key="save_bp_btn")
        if submitted:
            if not bp_name.strip():
                st.error("Brand name is required.")
            else:
                create_brand_profile({
                    "name": bp_name.strip(),
                    "voice": bp_voice.strip(),
                    "language": bp_language,
                    "target_market": bp_target.strip(),
                    "audience_age_group": bp_age,
                    "brand_colors": bp_colors.strip(),
                    "business_objective": bp_obj.strip(),
                    "words_to_avoid": bp_avoid.strip(),
                    "preferred_cta_style": bp_cta.strip(),
                    "is_active": bp_active,
                })
                st.toast("Brand profile created!", icon="🎨")
                st.rerun()

    # List Existing Profiles
    if all_profiles:
        st.subheader("Saved Brand Profiles")
        for bp in all_profiles:
            is_this_active = bp.get("is_active")
            badge = "🟢 ACTIVE" if is_this_active else "⚪ Inactive"

            with st.container(border=True):
                p_r1, p_r2 = st.columns([4, 1])
                with p_r1:
                    st.markdown(f"### {bp['name']} `{badge}`")
                    st.caption(f"**Voice:** {bp.get('voice', 'N/A')} | **Language:** {bp.get('language')} | **Target:** {bp.get('target_market', 'General')}")
                    if bp.get("brand_colors"):
                        st.markdown(f"**Visual Colors:** `{bp['brand_colors']}`")
                    if bp.get("words_to_avoid"):
                        st.markdown(f"**Forbidden Words:** _{bp['words_to_avoid']}_")
                    if bp.get("business_objective"):
                        st.markdown(f"**Objective:** {bp['business_objective']}")
                with p_r2:
                    if not is_this_active:
                        if st.button("Set Active", key=f"activate_{bp['id']}", use_container_width=True, type="primary"):
                            set_active_brand_profile(bp["id"])
                            st.toast(f"'{bp['name']}' is now the active brand profile!", icon="🟢")
                            st.rerun()

                    with st.popover("🗑️ Delete", use_container_width=True):
                        st.warning(f"Delete profile '{bp['name']}'?")
                        if st.button("Confirm Delete", key=f"del_bp_{bp['id']}", type="primary"):
                            delete_brand_profile(bp["id"])
                            st.toast("Brand profile deleted.", icon="🗑️")
                            st.rerun()


if __name__ == "__main__":
    import sys
    import uuid
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    st.set_page_config(page_title="Fission AI - Brand Profiles", page_icon="🎨", layout="wide")

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

    render_brand_page(show_nav=True)
