"""
Fission AI - Settings Page Module
Renders theme toggle (dark/light stored in session & app_settings),
API provider status, system check diagnostics, and cache management.
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional
import streamlit as st

from config.settings import (
    check_directories_writable,
    is_cloudflare_configured,
    is_gemini_key_set,
    is_groq_key_set,
    is_hf_token_set,
)
from database.db import get_db, get_setting, set_setting
from frontend.components.navigation import render_top_nav


def render_settings_page(show_nav: bool = False) -> None:
    """Render the Settings and Diagnostics view."""
    if show_nav:
        render_top_nav(active_page="settings")

    st.markdown('<div class="section-title">⚙️ Studio Settings & Diagnostics</div>', unsafe_allow_html=True)
    st.caption("Manage studio appearance, inspect API credentials, verify storage permissions, and clear generation caches.")

    # 1. APPEARANCE & DESIGN THEME
    st.markdown("### 🎨 Appearance & Design System")
    current_theme = st.session_state.get("theme", get_setting("theme", "dark"))
    theme_options = ["dark", "light"]
    theme_labels = {
        "dark": "🌙 Dark (Modern AI Studio - Default)",
        "light": "☀️ Light (Clean Studio)",
    }

    selected_theme = st.radio(
        "Studio Theme Mode",
        options=theme_options,
        index=0 if current_theme == "dark" else 1,
        format_func=lambda x: theme_labels[x],
        horizontal=True,
        help="Dark theme meets WCAG AAA standards for text contrast. Light theme provides high readability in bright environments."
    )

    if selected_theme != current_theme:
        set_setting("theme", selected_theme)
        st.session_state["theme"] = selected_theme
        st.toast(f"Theme switched to {selected_theme.title()} Mode!", icon="🎨")
        st.rerun()

    st.caption("Theme preference is saved to SQLite `app_settings` and preserved across studio restarts.")

    st.divider()

    # 2. API CREDENTIALS & ENGINE STATUS
    st.markdown("### 🔑 AI Provider Status")
    c1, c2 = st.columns(2)

    groq_ok = is_groq_key_set()
    cf_ok = is_cloudflare_configured()
    gemini_ok = is_gemini_key_set()
    hf_ok = is_hf_token_set()

    with c1:
        with st.container(border=True):
            st.markdown(f"#### Groq API (Text & Logic) {'✅' if groq_ok else '❌'}")
            st.caption(
                "Powers strategic idea generation, psychological hooks, tiered hashtags, "
                "quality scores, and 7/30-day content plans using `llama-3.3-70b-versatile`."
            )
            st.markdown(f"**Status:** `{'Configured & Active' if groq_ok else 'Missing GROQ_API_KEY in .env'}`")

        with st.container(border=True):
            st.markdown(f"#### Cloudflare Workers AI (Visuals) {'✅' if cf_ok else '❌'}")
            st.caption(
                "Runs dedicated serverless FLUX Schnell inference (`@cf/black-forest-labs/flux-1-schnell`) "
                "with 10,000 free Neurons/day (~300 free high-resolution images daily)."
            )
            st.markdown(f"**Status:** `{'Configured & Active' if cf_ok else 'Missing credentials in .env'}`")

    with c2:
        with st.container(border=True):
            st.markdown(f"#### Google Gemini API (Optional) {'✅' if gemini_ok else '⚪'}")
            st.caption(
                "Configured for Gemini Developer API. Note: Google Imagen 3 requires "
                "Vertex AI Enterprise Agent Platform credentials."
            )
            st.markdown(f"**Status:** `{'Configured' if gemini_ok else 'Not configured (Optional)'}`")

        with st.container(border=True):
            st.markdown(f"#### Hugging Face Inference {'✅' if hf_ok else '⚪'}")
            st.caption(
                "FLUX.1-schnell inference on Hugging Face requires paid Inference Credits ($0.003/image). "
                "The studio automatically falls back to Cloudflare or Free FLUX server."
            )
            st.markdown(f"**Status:** `{'Configured' if hf_ok else 'Not configured (Optional)'}`")

    st.divider()

    # 3. DATABASE & STORAGE DIAGNOSTICS
    st.markdown("### 💾 Storage & Database Diagnostics")
    writable_status = check_directories_writable()
    storage_all_ok = all(writable_status.values())

    d_c1, d_c2 = st.columns(2)
    with d_c1:
        st.markdown(f"**Python Runtime:** `{sys.version.split()[0]}`")
        st.markdown(f"**SQLite Database:** `data/fission.db`")
        with get_db() as conn:
            cur = conn.execute("SELECT MAX(version) FROM schema_version;")
            ver = cur.fetchone()[0]
            cur_items = conn.execute("SELECT COUNT(*) FROM content_items;").fetchone()[0]
            cur_brands = conn.execute("SELECT COUNT(*) FROM brand_profiles;").fetchone()[0]
        st.markdown(f"**Schema Migration Version:** `v{ver}`")
        st.markdown(f"**Database Records:** `{cur_items}` content items, `{cur_brands}` brand profiles")

    with d_c2:
        st.markdown(f"**Disk Storage Permission:** `{'✅ Writable' if storage_all_ok else '❌ Permission Denied'}`")
        st.markdown(f"**Audit Log File:** `data/logs/app.log` (rotating, secrets redacted)")
        log_path = Path("data/logs/app.log")
        if log_path.exists():
            st.markdown(f"**Log File Size:** `{round(log_path.stat().st_size / 1024, 1)} KB`")
        else:
            st.markdown("**Log File Size:** `0 KB`")

    st.divider()

    # 4. CACHE MANAGEMENT
    st.markdown("### 🧹 Cache & Session Reset")
    st.caption("Clear generated strategy ideas and visual caches from active browser session:")
    if st.button("🗑️ Clear Active Session Caches", type="secondary"):
        st.session_state.generated_result = None
        st.session_state.image_cache = {}
        st.session_state.active_content_plan = None
        st.toast("Session caches cleared!", icon="🧹")
        st.rerun()


if __name__ == "__main__":
    import sys
    import uuid
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    st.set_page_config(page_title="Fission AI - Settings & Diagnostics", page_icon="⚙️", layout="wide")

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

    render_settings_page(show_nav=True)

