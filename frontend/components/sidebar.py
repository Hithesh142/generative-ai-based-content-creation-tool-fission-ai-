"""
Fission AI - Sidebar Control Panel Component
Renders the left control panel: topic presets & custom focus, platform, audience, tone, format,
brand profile switcher with instant previews, primary generate action, and advanced options expander.
"""

import sys
from typing import Any, Dict, List, Optional, Tuple
import streamlit as st

from config.settings import (
    check_directories_writable,
    is_cloudflare_configured,
    is_gemini_key_set,
    is_groq_key_set,
    is_hf_token_set,
)
from database.db import (
    ensure_default_brand_profiles,
    get_active_brand_profile,
    get_distinct_values,
    list_brand_profiles,
    set_active_brand_profile,
)

# Curated high-converting topic presets across popular creator niches
CURATED_TOPICS = [
    "Placement Drive: Resume Building, Coding Rounds & HR Interview Prep",
    "AI Productivity Tools & Autonomous Workflows for Creators",
    "Calisthenics & Bodyweight Strength Progression",
    "Personal Finance & Smart Investing for College Students",
    "Micro-SaaS: From Zero to First $1K MRR",
    "Full-Stack Web Development Roadmap (MERN / Next.js)",
    "High-Protein Meal Prep & Nutrition Framework",
    "Mental Models & Critical Thinking Frameworks",
    "Creator Economy: Building & Monetizing a Newsletter",
]


def render_sidebar() -> Dict[str, Any]:
    """
    Render left studio control panel and return user configurations dictionary.
    """
    with st.sidebar:
        st.markdown(
            """
            <div style="margin-bottom: 12px;">
                <h2 style="margin: 0; font-size: 20px;">🎛️ Studio Control</h2>
                <span style="font-size: 13px; color: var(--fiss-text-muted, #A0A0B8);">Strategy & Visual Settings</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 1. Brand Profile Selector
        profiles = ensure_default_brand_profiles()
        active_prof = get_active_brand_profile()
        profile_names = ["None (Default)"] + [p["name"] for p in profiles]

        current_idx = 0
        if active_prof:
            for idx, p in enumerate(profiles, start=1):
                if p["id"] == active_prof["id"]:
                    current_idx = idx
                    break

        selected_p_name = st.selectbox(
            "Active Brand Profile",
            profile_names,
            index=current_idx,
            key="sb_brand_profile_select",
            help="Steers copy voice, target demographics, forbidden words, and visual palette across all AI tools."
        )

        # Handle brand switch if changed
        if selected_p_name == "None (Default)" and active_prof:
            from database.db import get_db
            with get_db() as conn:
                conn.execute("UPDATE brand_profiles SET is_active = 0;")
            st.rerun()
        elif selected_p_name != "None (Default)":
            matching = next((p for p in profiles if p["name"] == selected_p_name), None)
            if matching and (not active_prof or active_prof["id"] != matching["id"]):
                set_active_brand_profile(matching["id"])
                st.rerun()

        # Display rich active brand info card
        if active_prof:
            st.markdown(
                f"""
                <div style="padding: 8px 12px; background: var(--fiss-surface-raised, #1B1B2A); border-radius: 8px; border: 1px solid var(--fiss-border, #2A2A3D); font-size: 12px; margin-top: 4px; margin-bottom: 8px;">
                    <div>🎭 <b>Voice:</b> {active_prof.get('voice', 'Standard')}</div>
                    <div>🎯 <b>Target:</b> {active_prof.get('target_market', 'General')}</div>
                    <div>🎨 <b>Palette:</b> <span style="font-family: monospace;">{active_prof.get('brand_colors', 'Default')}</span></div>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.caption("ℹ️ Standard studio voice. Select a profile or create one in the **🎨 Brand** tab.")

        st.divider()

        # 2. Topic / Focus Options & Presets
        st.markdown("**🎯 Topic & Focus Area**")

        # Build combined list of curated presets and previously used database topics
        saved_db_topics = get_distinct_values("topic")
        extra_topics = [t for t in saved_db_topics if t and t not in CURATED_TOPICS]
        all_presets = ["-- Select a Topic Preset or Type Below --"] + CURATED_TOPICS + extra_topics

        # Callback helper to sync dropdown with text input
        def _on_topic_preset_change():
            sel = st.session_state.get("sb_preset_selector")
            if sel and sel != "-- Select a Topic Preset or Type Below --":
                st.session_state["sb_topic_input_value"] = sel
                # Auto-fill appropriate audience if placement drive
                if "placement drive" in sel.lower():
                    st.session_state["sb_audience_value"] = "College students & recent graduates preparing for placement drives"

        st.selectbox(
            "💡 Topic Options & Inspiration",
            options=all_presets,
            index=0,
            key="sb_preset_selector",
            on_change=_on_topic_preset_change,
            help="Choose a pre-tested high-engagement topic template or type your own below."
        )

        # Quick-Pick Topic Pills (One-Click)
        st.caption("Quick-pick tags:")
        q_c1, q_c2, q_c3 = st.columns(3)
        with q_c1:
            if st.button("🎓 Placement", key="btn_qp_placement", use_container_width=True):
                st.session_state["sb_topic_input_value"] = "Placement Drive: Resume Building, Coding Rounds & HR Interview Prep"
                st.session_state["sb_audience_value"] = "College students & job seekers preparing for campus recruitment"
                st.rerun()
        with q_c2:
            if st.button("🤖 AI Tools", key="btn_qp_ai", use_container_width=True):
                st.session_state["sb_topic_input_value"] = "AI Productivity Tools & Autonomous Workflows for Creators"
                st.session_state["sb_audience_value"] = "Creators, developers & tech enthusiasts"
                st.rerun()
        with q_c3:
            if st.button("💪 Fitness", key="btn_qp_fitness", use_container_width=True):
                st.session_state["sb_topic_input_value"] = "Calisthenics & Bodyweight Strength Progression"
                st.session_state["sb_audience_value"] = "Beginners & fitness enthusiasts"
                st.rerun()

        # Default topic value
        initial_topic = st.session_state.get("sb_topic_input_value", "Placement Drive: Resume Building, Coding Rounds & HR Interview Prep")

        topic = st.text_input(
            "Topic / Focus *",
            value=initial_topic,
            placeholder="e.g. Placement Drive, Calisthenics Strength",
            help="What do you want to create content about? Select from options above or customize freely.",
            key="sb_topic_input"
        )
        # Keep session state in sync
        st.session_state["sb_topic_input_value"] = topic

        platform = st.selectbox(
            "Platform",
            ["Instagram", "LinkedIn", "Twitter / X", "YouTube Shorts", "TikTok", "Blog Post", "Newsletter"],
            index=0,
            key="sb_platform_select"
        )

        # Auto-fill audience from brand profile or topic preset
        default_aud = (
            st.session_state.get("sb_audience_value")
            or (active_prof.get("target_market", "") if active_prof else "General Audience")
        )
        audience = st.text_input(
            "Target Audience",
            value=default_aud,
            placeholder="e.g. Founders, Beginners, College Students",
            key="sb_audience_input"
        )

        c_col1, c_col2 = st.columns(2)
        with c_col1:
            tone = st.selectbox(
                "Tone",
                ["Professional", "Casual", "Educational", "Inspirational", "Humorous", "Bold & Direct"],
                index=0,
                key="sb_tone_select"
            )
        with c_col2:
            content_type = st.selectbox(
                "Format",
                ["Post", "Carousel", "Reel / Short", "Thread", "Long Article"],
                index=0,
                key="sb_format_select"
            )

        number_of_ideas = st.slider("Ideas Count", min_value=1, max_value=10, value=5, key="sb_ideas_count_slider")

        # Primary Generate Button
        generate_clicked = st.button("✨ Generate Strategy", type="primary", use_container_width=True, key="sb_generate_btn")

        # Collapsed Advanced Options Expander
        with st.expander("⚙️ Advanced Parameters & Visual Engine", expanded=False):
            keywords = st.text_input("Keywords / SEO Tags", placeholder="e.g. aptitude, technical interview, dsa", key="sb_keywords_input")
            objective = st.selectbox(
                "Campaign Objective",
                ["None", "Brand Awareness", "Lead Generation", "Product Launch", "Audience Engagement", "Authority Building"],
                index=0,
                key="sb_objective_select"
            )

            image_engine = st.selectbox(
                "Image Engine",
                [
                    "Cloudflare Workers AI (10,000 Free Neurons/Day)",
                    "Free Engine (FLUX - Public Server)",
                    "Auto (Smart Multi-Engine Fallback)",
                    "Google Imagen 3 (Vertex AI)",
                    "Hugging Face (Paid Inference Credits)",
                ],
                index=0,
                key="sb_engine_select",
                help="Cloudflare Workers AI runs dedicated serverless FLUX Schnell inference with 10k free Neurons/day."
            )

        # System Diagnostics
        st.divider()
        with st.expander("🔍 System Diagnostics", expanded=False):
            py_ver = sys.version.split()[0]
            groq_ok = is_groq_key_set()
            cf_ok = is_cloudflare_configured()
            hf_ok = is_hf_token_set()
            storage_ok = all(check_directories_writable().values())

            st.caption(f"**Python:** `{py_ver}`")
            st.caption(f"**Groq:** {'✅ Ready' if groq_ok else '❌ Missing'}")
            st.caption(f"**Cloudflare:** {'✅ Ready' if cf_ok else '❌ Missing'}")
            st.caption(f"**HF Token:** {'✅ Ready' if hf_ok else '⚪ Optional'}")
            st.caption(f"**SQLite Storage:** {'✅ Writable' if storage_ok else '❌ Read-Only'}")

        return {
            "topic": topic,
            "platform": platform,
            "audience": audience,
            "tone": tone,
            "content_type": content_type,
            "number_of_ideas": number_of_ideas,
            "keywords": keywords,
            "campaign_objective": objective if objective != "None" else None,
            "image_engine": image_engine,
            "generate_clicked": generate_clicked,
            "active_brand": active_prof,
        }
