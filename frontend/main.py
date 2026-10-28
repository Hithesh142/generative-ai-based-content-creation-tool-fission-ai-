"""
Fission AI - Modern AI Creative Studio
Main application entrypoint. Coordinates layout, navigation tabs,
centralized CSS design system, and delegates to modular pages.
"""

import sys
import uuid
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st

from config.logging_config import get_logger
from database.db import (
    ensure_default_brand_profiles,
    get_active_brand_profile,
    get_setting,
    init_db,
)
from frontend.components.header import render_header
from frontend.components.sidebar import render_sidebar
from frontend.pages.brand import render_brand_page
from frontend.pages.calendar import render_calendar_page
from frontend.pages.library import render_library_page
from frontend.pages.settings import render_settings_page
from frontend.pages.studio import render_studio_page
from frontend.styles import get_css
from services.content_generator import generate_content_ideas

logger = get_logger("frontend.main")

# =========================================================
# PAGE CONFIGURATION & DATABASE INITIALIZATION
# =========================================================

st.set_page_config(
    page_title="Fission AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database schema, migrations, and seed default brand profiles
init_db()
ensure_default_brand_profiles()


# =========================================================
# SESSION STATE & THEME INITIALIZATION
# =========================================================

if "theme" not in st.session_state:
    st.session_state["theme"] = get_setting("theme", "dark")

if "generated_result" not in st.session_state:
    st.session_state.generated_result = None

if "generated_topic" not in st.session_state:
    st.session_state.generated_topic = ""

if "generated_platform" not in st.session_state:
    st.session_state.generated_platform = ""

if "generated_audience" not in st.session_state:
    st.session_state.generated_audience = ""

if "image_cache" not in st.session_state:
    st.session_state.image_cache = {}

if "generation_id" not in st.session_state:
    st.session_state.generation_id = "initial"


# =========================================================
# INJECT CENTRALIZED DESIGN SYSTEM CSS
# =========================================================

theme_mode = st.session_state.get("theme", "dark")
st.markdown(get_css(theme=theme_mode), unsafe_allow_html=True)


# =========================================================
# HEADER & SIDEBAR CONTROLS
# =========================================================

active_brand = get_active_brand_profile()
render_header(active_brand=active_brand)
sidebar_inputs = render_sidebar()


# =========================================================
# STRATEGY GENERATION HANDLER
# =========================================================

if sidebar_inputs.get("generate_clicked"):
    topic_val = sidebar_inputs.get("topic", "").strip()
    if not topic_val:
        st.warning("⚠️ Please enter a Topic or Focus keyword in the left Studio Control panel before generating.")
    else:
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
            logger.error(f"Strategy generation failed: {e}")
            st.error(f"❌ Strategy generation error: {str(e)}")


# =========================================================
# MAIN NAVIGATION TABS
# =========================================================

tab_studio, tab_library, tab_calendar, tab_brand, tab_settings = st.tabs([
    "🚀 Studio",
    "📚 Library",
    "📅 Calendar",
    "🎨 Brand",
    "⚙️ Settings"
])

with tab_studio:
    render_studio_page(sidebar_inputs=sidebar_inputs)

with tab_library:
    render_library_page()

with tab_calendar:
    render_calendar_page()

with tab_brand:
    render_brand_page()

with tab_settings:
    render_settings_page()


# =========================================================
# MINIMAL STUDIO FOOTER
# =========================================================

st.divider()
st.caption("Fission AI • Modern AI Creative Studio • Linear / Notion / Midjourney Aesthetic • WCAG AA Compliant")
