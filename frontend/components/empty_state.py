"""
Fission AI - Empty State Component
Renders lightweight, friendly empty state cards using inline SVG/emojis with clear calls to action.
"""

from typing import Callable, Optional
import streamlit as st


def render_empty_state(
    title: str = "No content generated yet",
    description: str = "Configure your topic in the left control panel and generate your first strategy.",
    button_label: Optional[str] = "✨ Generate your first strategy",
    on_click: Optional[Callable] = None,
    icon: str = "🪄",
    key: Optional[str] = None,
) -> bool:
    """
    Render a clean empty state card.
    Returns True if the action button was clicked.
    """
    with st.container(border=True):
        st.markdown(
            f"""
            <div style="text-align: center; padding: 36px 16px;">
                <div style="font-size: 48px; margin-bottom: 12px;">{icon}</div>
                <h3 style="margin-bottom: 8px;">{title}</h3>
                <p style="color: var(--fiss-text-muted, #A0A0B8); max-width: 480px; margin: 0 auto 24px auto;">
                    {description}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        if button_label:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                btn_key = key or f"empty_state_btn_{hash((title, button_label))}"
                if st.button(button_label, key=btn_key, type="primary", use_container_width=True):
                    if on_click:
                        on_click()
                    return True
    return False
