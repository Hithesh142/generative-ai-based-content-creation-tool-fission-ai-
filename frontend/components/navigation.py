"""
Fission AI - Top Navigation Bar Component
Renders a consistent horizontal navigation bar across all application pages.
"""

from typing import Optional
import streamlit as st


def render_top_nav(active_page: str = "studio") -> None:
    """
    Render top navigation bar allowing seamless switching between Studio, Calendar, Library, Brand, and Settings.
    Works seamlessly both in multi-page mode and when running pages standalone or in tests.
    """
    c1, c2, c3, c4, c5 = st.columns(5)

    pages = [
        (c1, "main.py", "🚀 Studio", active_page == "studio"),
        (c2, "pages/calendar.py", "📅 Calendar", active_page == "calendar"),
        (c3, "pages/library.py", "📚 Library", active_page == "library"),
        (c4, "pages/brand.py", "🎨 Brand", active_page == "brand"),
        (c5, "pages/settings.py", "⚙️ Settings", active_page == "settings"),
    ]

    for col, target, label, is_active in pages:
        with col:
            try:
                st.page_link(target, label=label, use_container_width=True)
            except Exception:
                # Graceful fallback for test runners or standalone page execution
                st.button(label, key=f"nav_fallback_{target}_{label}", use_container_width=True, disabled=is_active)

    st.markdown(
        "<hr style='margin-top: 8px; margin-bottom: 16px; border: 0; border-top: 1px solid var(--fiss-border, #2A2A3D);' />",
        unsafe_allow_html=True,
    )
