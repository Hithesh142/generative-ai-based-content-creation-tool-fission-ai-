# ⚡ Fission AI — Modern AI Creative Studio

> **From idea to image, in one studio.**  
> Autonomous AI Content Strategy, Visual Studio, Editorial Calendar & SQLite Knowledge Base.  
> Designed with a Linear / Notion / Midjourney aesthetic, WCAG AA compliance, and modular architecture.

---

## 🌟 Overview

**Fission AI** is a professional-grade creative studio that transforms high-level themes into platform-optimized content campaigns, psychological hooks, and high-resolution visuals. Backed by **Groq** (`llama-3.3-70b-versatile`), serverless **Cloudflare Workers AI** (FLUX Schnell), and an embedded **SQLite Knowledge Base**, Fission AI empowers creators, growth teams, and founders to brainstorm, visualize, schedule, and export multi-platform campaigns from a unified workspace.

---

## ✨ Key Features & Capabilities

### 1. 🚀 Strategic Content Studio
- **Multi-Angle Strategy Generation:** Generates 1 to 10 structured concepts per run tailored to platform, tone, audience demographics, and campaign objectives.
- **7-Day & 30-Day Automated Content Plans:** Generates complete editorial roadmaps with format rotation (Posts, Carousels, Short Scripts, Articles) with 1-click bulk save to Library and Calendar.
- **Psychological Hook Variants:** Generates 5 distinct psychological angles (Curiosity Gap, Contrarian, Problem-Agitation, Data-Driven, Storytelling) with rationales.
- **Caption Polish & Translator:** Instant adaptations across styles (*Shorten, Bold, Professional, Storytelling*) and multi-lingual translation (*Spanish, French, German, Hindi, Portuguese, Japanese*).
- **Tiered Hashtag Engine:** Research-backed Niche, Trending, and Branded hashtag tiers deduplicated and clamped to platform best practices.
- **Content Quality Auditor:** Groq-evaluated 0–100 score across Hook Strength, Clarity, CTA Effectiveness, and Platform Fit with actionable recommendations.
- **Cross-Platform Repurposing:** 1-click adaptation of ideas across LinkedIn, Twitter/X, TikTok, YouTube Shorts, and Newsletters.

### 2. 🖼️ Visual Composition Studio
- **Serverless FLUX Schnell (Cloudflare Workers AI):** Dedicated 4-step distilled FLUX generation with **10,000 free Neurons/day** (~300 free high-res visuals daily).
- **Multi-Engine Smart Fallback:** Seamless fallback pipeline: `Cloudflare Workers AI -> Hugging Face FLUX.1 -> Free Public FLUX Engine`.
- **AI Prompt Enhancer:** Injects lighting, lens specs, composition geometry, and active brand color grading.
- **Multiple Visual Variations:** Generates 3 alternative visual compositions in a grid with 1-click selection and attachment.
- **Visual Lightbox:** Modal inspection with model metadata, resolution, and one-click PNG download.
- **Recent Generations Strip:** Quick-access carousel of previously rendered artwork.

### 3. 📅 Editorial Calendar & RFC 5545 Export
- **Upcoming Schedule & 7-Day Views:** Real-time metrics for Overdue, Upcoming, Published, and Backlog items.
- **Quick Reschedule & Status Updates:** Interactive popover to update dates, post times, status pills, and editorial notes.
- **Standard Calendar Export:** One-click export to standard `.ics` (RFC 5545 compliant for Google Calendar, Apple Calendar, and Outlook) and calendar CSV.

### 4. 📚 SQLite Library & Knowledge Base
- **Robust Persistence:** SQLite with parameterized queries, schema versioning, and automated migrations (`data/fission.db`).
- **Comprehensive Search & Filters:** Search by topic, headline, hook, or caption; filter by platform, status (*Draft, Planned, Ready, Published*), and sort order.
- **Visual Gallery View:** Grid inspection of saved artwork and creative assets.
- **Enterprise-Grade Exports:**
  - Single caption TXT with safe slugified filenames.
  - Full Library CSV with UTF-8 BOM encoding for seamless Microsoft Excel compatibility.
  - Complete JSON campaign schemas.
  - Automated ZIP bundles containing images, captions, and CSV manifest.

### 5. 🎨 Brand Identity Profiles
- **Style Steering:** Define brand voice, language, target demographics, brand visual palette (hex codes), forbidden negative keywords, and preferred CTA styles.
- **Automated Injection:** Active profile dynamically guides Groq system prompts and visual color grading across all studio tools.

### 6. ⚙️ Studio Appearance & Diagnostics
- **Design System:** Centralized CSS with CSS variables (`--fiss-accent: #7C5CFF`, `--fiss-bg: #0B0B12`, etc.), Google Fonts (*Sora, Inter, JetBrains Mono*), and card hover transitions.
- **Light / Dark Mode Switcher:** Studio theme toggle stored in session state and persisted in SQLite `app_settings`.
- **WCAG AA Compliance:** Body text contrast ratios exceed 17:1 in both dark and light modes.
- **Telemetry & Secret Redaction:** Centralized rotating audit logging (`data/logs/app.log`) with automated masking of API keys and account tokens.

---

## 🛠️ Architecture & Project Structure

```
fission_ai/
├── .streamlit/
│   └── config.toml                # Dark theme base configuration & server options
├── config/
│   ├── logging_config.py          # Rotating file logger with secret redaction
│   └── settings.py                # Environment variable parsing and directory validation
├── database/
│   ├── __init__.py
│   └── db.py                      # SQLite connection pool, schema migrations v1-v3, CRUD
├── frontend/
│   ├── components/
│   │   ├── __init__.py
│   │   ├── empty_state.py         # SVG/emoji empty state cards with action buttons
│   │   ├── header.py              # Gradient wordmark and active brand pill
│   │   ├── idea_card.py           # @st.fragment idea card with @st.dialog lightbox
│   │   ├── metrics.py             # 4-tile studio telemetry dashboard strip
│   │   └── sidebar.py             # Left control panel with brand switcher & advanced options
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── brand.py               # Brand profiles CRUD & active profile switcher
│   │   ├── calendar.py            # Editorial calendar views, metrics, & RFC 5545 export
│   │   ├── library.py             # SQLite library, search/filter, gallery, & bulk exports
│   │   ├── settings.py            # Dark/light toggle, API diagnostics, cache reset
│   │   └── studio.py              # 7/30-day planner, 2-column card grid, recent visuals
│   ├── main.py                    # Thin entrypoint coordinating layout, CSS, & navigation
│   └── styles.py                  # Centralized CSS design system & WCAG AA contrast tools
├── services/
│   ├── ai_tools.py                # 7-day plan, hook variants, rewriter, hashtags, audit, repurpose
│   ├── content_generator.py       # Groq strategy generation with Pydantic validation
│   ├── exporter.py                # TXT, CSV (with BOM), JSON, ZIP, and RFC 5545 .ics exporters
│   └── image_generator.py         # Cloudflare Workers AI FLUX Schnell, HF, Free Engine, Enhancer
├── tests/
│   ├── test_image_generator.py    # Image engine fallbacks, retries, auth errors, aspect ratios
│   ├── test_phase1.py             # Groq parser, JSON extraction, schema fallbacks
│   ├── test_phase3.py             # SQLite CRUD, migrations, filters, exports, persistence proof
│   ├── test_phase4.py             # Calendar metrics, brand injection, .ics export, logger redaction
│   ├── test_ui.py                 # Streamlit AppTest smoke tests, theme persistence, WCAG AA tests
│   └── test_live_integration.py   # Live API test (marked with @pytest.mark.live, skipped by default)
├── .env.example                   # Environment configuration template
├── pytest.ini                     # Pytest settings (addopts = -m "not live")
├── requirements.txt               # Pinned dependencies
├── DEPLOYMENT.md                  # Streamlit Cloud & Docker deployment guide
└── MANUAL_TEST_CHECKLIST.md       # Quality assurance verification protocols
```

---

## ⚡ Quickstart (Windows PowerShell)

### 1. Prerequisites
- Python 3.10+ (Tested on Python 3.12.5)
- Git

### 2. Clone and Setup Environment
```powershell
# Clone repository
git clone https://github.com/Hithesh142/generative-ai-based-content-creation-tool-fission-ai-.git
cd generative-ai-based-content-creation-tool-fission-ai-

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and configure your API credentials:
```powershell
Copy-Item .env.example .env
notepad .env
```

Set your API keys:
```ini
# Required for text strategy and AI professional suite
GROQ_API_KEY=gsk_your_groq_api_key_here

# Recommended for high-speed serverless visual rendering (~300 free images/day)
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id_here
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token_here

# Optional: Google Gemini Developer API
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Hugging Face (Inference credits required for FLUX)
HF_TOKEN=hf_your_huggingface_token_here
```

### 4. Launch the Studio
```powershell
.venv\Scripts\streamlit.exe run frontend/main.py
```
Open your browser to `http://localhost:8501`.

---

## 📊 Free-Tier Model Limits & Cost Reference (October 2026)

| Provider | Model / Endpoint | Free Tier Allowance | Paid Rate After Allowance | Recommended Use |
|:---|:---|:---|:---|:---|
| **Groq** | `llama-3.3-70b-versatile` | 30 requests/min, 14,400 req/day | Pay-as-you-go (~$0.59/M tokens) | All copy, hooks, hashtags, plans, audits |
| **Cloudflare Workers AI** | `@cf/black-forest-labs/flux-1-schnell` | **10,000 free Neurons/day** (~300 images/day) | $0.011 per 1,000 Neurons (~$0.0003/image) | **Primary Visual Engine** |
| **Hugging Face** | `black-forest-labs/FLUX.1-schnell` | Free tier routes via third-party providers requiring paid inference credits | ~$0.003 / image | Secondary fallback |
| **Free FLUX Engine** | Public Serverless FLUX Endpoint | Community server | Free (Subject to rate-limits/concurrency) | Zero-credential automatic fallback |
| **Google Gemini API** | `gemini-2.0-flash` | Free tier available for chat/completions | Tier-dependent | Chat/Analysis (*Note: Imagen 3 requires Vertex AI Enterprise mode*) |

---

## 🧪 Running Automated Tests

Run the full automated test suite with standard mocked APIs:
```powershell
.venv\Scripts\pytest.exe -v
```

Run only the Streamlit UI smoke tests:
```powershell
.venv\Scripts\pytest.exe tests/test_ui.py -v
```

Run live integration tests (requires valid keys in `.env`):
```powershell
.venv\Scripts\pytest.exe -m live -v
```

---

## 🔧 Troubleshooting Guide

| Issue | Cause | Resolution |
|:---|:---|:---|
| `Groq API Key Missing` | `.env` file not created or key missing | Create `.env` from `.env.example` and set `GROQ_API_KEY=gsk_...`. Restart Streamlit. |
| `Cloudflare Workers AI returns 401/403` | Invalid Token or Account ID | Verify `CLOUDFLARE_ACCOUNT_ID` in Cloudflare dashboard URL and verify token has `Workers AI: Read` permission. |
| `Hugging Face returns HTTP 402 Payment Required` | HF requires paid inference credits for FLUX.1 | Switch image engine to **Cloudflare Workers AI** (10k free daily Neurons) or **Free Engine** in the studio sidebar. |
| `Database is locked` | Simultaneous SQLite writes | Fission AI configures SQLite `PRAGMA busy_timeout = 5000;` and WAL mode automatically. Close any external database viewer. |
| `CSV characters garbled in Excel` | Excel default ANSI encoding | Fission AI exports CSV files with a **UTF-8 Byte Order Mark (BOM)** automatically so Excel opens them cleanly. |
| `App loads slowly on initial run` | Downloading Google Fonts | The design system imports *Sora*, *Inter*, and *JetBrains Mono* with instant system-ui fallbacks (`-apple-system, Segoe UI, sans-serif`). |

---

## 📄 License

Apache License 2.0. Built with pride for creator economy workflows.
