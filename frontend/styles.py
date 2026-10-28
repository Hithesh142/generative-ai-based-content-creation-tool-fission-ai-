"""
Fission AI - Design System & Global Styles
Implements "Modern AI Creative Studio" aesthetic (Linear / Notion / Midjourney).
Supports CSS variables on :root, light/dark mode switching, WCAG AA compliance,
Google Fonts (Sora, Inter, JetBrains Mono), pure CSS skeleton shimmer, and 8px spacing scale.
"""

from typing import Any, Dict, Tuple

# ============================================================
# WCAG AA COLOR CONTRAST UTILITIES
# ============================================================

def _hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_clean = hex_code.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    return (int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16))


def _relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Calculate relative luminance according to WCAG 2.1 specifications."""
    def channel_lum(val: int) -> float:
        c = val / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)


def calculate_contrast_ratio(hex_foreground: str, hex_background: str) -> float:
    """Calculate contrast ratio between two hex colors (1.0 to 21.0)."""
    lum1 = _relative_luminance(_hex_to_rgb(hex_foreground))
    lum2 = _relative_luminance(_hex_to_rgb(hex_background))
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def get_contrast_report() -> Dict[str, Dict[str, Any]]:
    """Verify WCAG AA compliance (4.5:1 for body text, 3.0:1 for graphical UI elements/buttons)."""
    checks = {
        "Dark Mode: Body Text (#F2F2F7 on #0B0B12)": ("#F2F2F7", "#0B0B12", 4.5),
        "Dark Mode: Muted Text (#A0A0B8 on #0B0B12)": ("#A0A0B8", "#0B0B12", 4.5),
        "Dark Mode: Surface Text (#F2F2F7 on #14141F)": ("#F2F2F7", "#14141F", 4.5),
        "Dark Mode: Muted on Surface (#A0A0B8 on #14141F)": ("#A0A0B8", "#14141F", 4.5),
        "Dark Mode: Accent Button Text (#FFFFFF on #7C5CFF)": ("#FFFFFF", "#7C5CFF", 3.0),
        "Dark Mode: Success Pill (#2DD4A0 on #14141F)": ("#2DD4A0", "#14141F", 3.0),
        "Dark Mode: Warning Pill (#FFB020 on #14141F)": ("#FFB020", "#14141F", 3.0),
        "Dark Mode: Error Pill (#FF5C7A on #14141F)": ("#FF5C7A", "#14141F", 3.0),
        "Light Mode: Body Text (#14141F on #F7F7FB)": ("#14141F", "#F7F7FB", 4.5),
        "Light Mode: Muted Text (#5C5C70 on #FFFFFF)": ("#5C5C70", "#FFFFFF", 4.5),
        "Light Mode: Accent Button Text (#FFFFFF on #7C5CFF)": ("#FFFFFF", "#7C5CFF", 3.0),
    }
    report = {}
    for name, (fg, bg, target) in checks.items():
        ratio = calculate_contrast_ratio(fg, bg)
        report[name] = {"ratio": ratio, "target": target, "compliant": ratio >= target}
    return report


# ============================================================
# CSS DESIGN SYSTEM
# ============================================================

def get_css(theme: str = "dark") -> str:
    """
    Generate unified CSS stylesheet for the application.
    Supports 'dark' and 'light' modes.
    """
    is_light = (theme.lower() == "light")

    if is_light:
        bg_color = "#F7F7FB"
        surface_color = "#FFFFFF"
        surface_raised = "#F0F0F7"
        border_color = "#E3E3EE"
        text_color = "#14141F"
        text_muted = "#5C5C70"
        card_shadow = "0 2px 12px rgba(20, 20, 31, 0.06)"
        shimmer_bg = "linear-gradient(90deg, #EBEBF5 0%, #F5F5FA 50%, #EBEBF5 100%)"
    else:
        bg_color = "#0B0B12"
        surface_color = "#14141F"
        surface_raised = "#1B1B2A"
        border_color = "#2A2A3D"
        text_color = "#F2F2F7"
        text_muted = "#A0A0B8"
        card_shadow = "0 4px 20px rgba(0, 0, 0, 0.35)"
        shimmer_bg = "linear-gradient(90deg, #1B1B2A 0%, #2A2A3D 50%, #1B1B2A 100%)"

    css = f"""
    <style>
    /* Google Fonts import */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Sora:wght@600;700;800&display=swap');

    :root {{
        --fiss-bg: {bg_color};
        --fiss-surface: {surface_color};
        --fiss-surface-raised: {surface_raised};
        --fiss-border: {border_color};
        --fiss-text: {text_color};
        --fiss-text-muted: {text_muted};
        --fiss-accent: #7C5CFF;
        --fiss-accent-gradient: linear-gradient(135deg, #7C5CFF 0%, #00D1FF 100%);
        --fiss-success: #2DD4A0;
        --fiss-warning: #FFB020;
        --fiss-error: #FF5C7A;
        --fiss-info: #4DA3FF;
        --fiss-card-radius: 16px;
        --fiss-btn-radius: 10px;
        --fiss-font-heading: 'Sora', Inter, system-ui, sans-serif;
        --fiss-font-body: 'Inter', system-ui, -apple-system, Segoe UI, sans-serif;
        --fiss-font-mono: 'JetBrains Mono', Consolas, monospace;
    }}

    /* Global Typography & Background */
    html, body, [data-testid="stAppViewContainer"] {{
        background-color: var(--fiss-bg) !important;
        color: var(--fiss-text) !important;
        font-family: var(--fiss-font-body);
        font-size: 16px;
        line-height: 1.6;
    }}

    /* Hide default Streamlit Chrome safely */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{
        background: transparent !important;
    }}

    /* Fix top clipping by giving the main container proper clearance below header */
    .block-container {{
        padding-top: 4.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 1350px !important;
    }}

    /* Headings */
    h1, h2, h3 {{
        font-family: var(--fiss-font-heading) !important;
        color: var(--fiss-text) !important;
        letter-spacing: -0.02em;
    }}
    h1 {{ font-size: 32px !important; font-weight: 800; }}
    h2 {{ font-size: 24px !important; font-weight: 700; }}
    h3 {{ font-size: 18px !important; font-weight: 600; }}

    /* Sidebar Control Panel */
    [data-testid="stSidebar"] {{
        background-color: var(--fiss-surface) !important;
        border-right: 1px solid var(--fiss-border) !important;
        padding-top: 1rem;
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
        color: var(--fiss-text) !important;
    }}

    /* Sidebar Navigation Links */
    [data-testid="stSidebarNav"] {{
        padding-top: 0.5rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--fiss-border);
        margin-bottom: 1rem;
    }}
    [data-testid="stSidebarNav"] ul {{
        gap: 4px;
    }}
    [data-testid="stSidebarNav"] a {{
        border-radius: 8px !important;
        padding: 6px 12px !important;
        font-family: var(--fiss-font-heading) !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        color: var(--fiss-text-muted) !important;
        transition: all 0.15s ease !important;
    }}
    [data-testid="stSidebarNav"] a:hover {{
        background-color: var(--fiss-surface-raised) !important;
        color: var(--fiss-text) !important;
    }}
    [data-testid="stSidebarNav"] a[aria-current="page"] {{
        background-color: rgba(124, 92, 255, 0.15) !important;
        color: #00D1FF !important;
        border-left: 3px solid #7C5CFF !important;
    }}

    /* Tabs Styling - Gradient Active Indicator */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {{
        background-color: transparent !important;
        border-bottom: 1px solid var(--fiss-border) !important;
        gap: 8px;
    }}
    [data-testid="stTabs"] button[data-baseweb="tab"] {{
        font-family: var(--fiss-font-heading) !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        color: var(--fiss-text-muted) !important;
        background-color: transparent !important;
        border: none !important;
        padding: 10px 18px !important;
        border-radius: 8px 8px 0 0 !important;
        transition: all 0.2s ease;
    }}
    [data-testid="stTabs"] button[data-baseweb="tab"]:hover {{
        color: var(--fiss-text) !important;
    }}
    [data-testid="stTabs"] button[aria-selected="true"] {{
        color: var(--fiss-text) !important;
        border-bottom: 3px solid #7C5CFF !important;
        border-image: var(--fiss-accent-gradient) 1 !important;
    }}

    /* Buttons: Primary Gradient vs Ghost/Secondary */
    .stButton > button[kind="primary"] {{
        background: var(--fiss-accent-gradient) !important;
        color: #FFFFFF !important;
        font-family: var(--fiss-font-heading) !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: var(--fiss-btn-radius) !important;
        padding: 10px 20px !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        box-shadow: 0 4px 14px rgba(124, 92, 255, 0.35);
    }}
    .stButton > button[kind="primary"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(124, 92, 255, 0.45);
    }}

    .stButton > button:not([kind="primary"]) {{
        background-color: var(--fiss-surface-raised) !important;
        color: var(--fiss-text) !important;
        border: 1px solid var(--fiss-border) !important;
        border-radius: var(--fiss-btn-radius) !important;
        font-weight: 500 !important;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }}
    .stButton > button:not([kind="primary"]):hover {{
        transform: translateY(-2px);
        border-color: var(--fiss-accent) !important;
    }}

    /* Focus visible accessibility */
    button:focus-visible, input:focus-visible, textarea:focus-visible {{
        outline: 2px solid var(--fiss-accent) !important;
        outline-offset: 2px !important;
    }}

    /* Card Containers */
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: var(--fiss-surface) !important;
        border: 1px solid var(--fiss-border) !important;
        border-radius: var(--fiss-card-radius) !important;
        box-shadow: {card_shadow} !important;
        padding: 18px !important;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }}
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        border-color: #3B3B52 !important;
    }}

    /* Hook Highlight Banner */
    .hook-callout {{
        border-left: 3px solid var(--fiss-accent);
        background-color: var(--fiss-surface-raised);
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        font-size: 17px;
        font-weight: 600;
        color: var(--fiss-text);
        margin: 12px 0;
    }}

    /* Badges & Chips */
    .fiss-chip {{
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
        border: 1px solid var(--fiss-border);
        background-color: var(--fiss-surface-raised);
        color: var(--fiss-text-muted);
    }}
    .fiss-chip-status-draft {{
        background-color: rgba(255, 176, 32, 0.12);
        color: var(--fiss-warning);
        border-color: rgba(255, 176, 32, 0.3);
    }}
    .fiss-chip-status-ready {{
        background-color: rgba(45, 212, 160, 0.12);
        color: var(--fiss-success);
        border-color: rgba(45, 212, 160, 0.3);
    }}
    .fiss-chip-status-planned {{
        background-color: rgba(77, 163, 255, 0.12);
        color: var(--fiss-info);
        border-color: rgba(77, 163, 255, 0.3);
    }}
    .fiss-chip-status-published {{
        background-color: rgba(124, 92, 255, 0.12);
        color: var(--fiss-accent);
        border-color: rgba(124, 92, 255, 0.3);
    }}

    /* Metric Tiles */
    [data-testid="stMetric"] {{
        background-color: var(--fiss-surface) !important;
        border: 1px solid var(--fiss-border) !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: var(--fiss-text-muted) !important;
        font-size: 13px !important;
        font-weight: 600 !important;
    }}
    [data-testid="stMetricValue"] {{
        color: var(--fiss-text) !important;
        font-family: var(--fiss-font-heading) !important;
        font-weight: 800 !important;
    }}

    /* CSS Skeleton Shimmer Placeholder */
    @keyframes shimmer {{
        0% {{ background-position: -200% 0; }}
        100% {{ background-position: 200% 0; }}
    }}
    .skeleton-placeholder {{
        width: 100%;
        aspect-ratio: 1 / 1;
        background: {shimmer_bg};
        background-size: 200% 100%;
        animation: shimmer 1.8s infinite ease-in-out;
        border-radius: 12px;
        border: 1px dashed var(--fiss-border);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: var(--fiss-text-muted);
        font-size: 14px;
        font-weight: 500;
        gap: 8px;
    }}
    @media (prefers-reduced-motion: reduce) {{
        .skeleton-placeholder {{
            animation: none;
            background: var(--fiss-surface-raised);
        }}
    }}

    /* Mobile Responsive Optimizations (<768px) */
    @media (max-width: 768px) {{
        .stButton > button {{
            min-height: 44px !important;
            width: 100% !important;
            font-size: 16px !important;
        }}
        [data-testid="stMetric"] {{
            margin-bottom: 8px;
        }}
        .hook-callout {{
            font-size: 15px;
        }}
    }}
    </style>
    """
    return css
