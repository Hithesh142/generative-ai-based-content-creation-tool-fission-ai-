"""
Fission AI - Branded Header Component
Renders the top application wordmark with accent gradient and active brand pill.
"""

from typing import Any, Dict, Optional
import streamlit as st


def render_header(active_brand: Optional[Dict[str, Any]] = None) -> None:
    """Render the top banner with gradient logo wordmark and studio tagline."""
    col_logo, col_pill = st.columns([3, 2])

    with col_logo:
        st.markdown(
            """
            <div style="margin-top: 4px; margin-bottom: 2px;">
                <span style="
                    display: inline-block;
                    line-height: 1.25;
                    padding: 2px 0;
                    font-family: 'Sora', sans-serif;
                    font-size: 38px;
                    font-weight: 800;
                    letter-spacing: -0.03em;
                    background: linear-gradient(135deg, #7C5CFF 0%, #00D1FF 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                ">FISSION AI</span>
            </div>
            <div style="
                font-size: 15px;
                color: var(--fiss-text-muted, #A0A0B8);
                margin-bottom: 18px;
                font-weight: 500;
            ">From idea to image, in one studio.</div>
            """,
            unsafe_allow_html=True
        )

    with col_pill:
        if active_brand:
            brand_name = active_brand.get("name", "Active Brand")
            voice = active_brand.get("voice", "Default Voice")
            st.markdown(
                f"""
                <div style="text-align: right; padding-top: 10px;">
                    <span class="fiss-chip" style="border-left: 3px solid #7C5CFF; background-color: var(--fiss-surface-raised, #1B1B2A);">
                        🎨 <b>{brand_name}</b> • <span style="font-style: italic; opacity: 0.85;">{voice}</span>
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                """
                <div style="text-align: right; padding-top: 10px;">
                    <span class="fiss-chip" style="border-left: 3px solid #A0A0B8; background-color: var(--fiss-surface-raised, #1B1B2A);">
                        🎨 <b>Default Brand Profile</b> • <span style="font-style: italic; opacity: 0.85;">Standard Studio Voice</span>
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )
