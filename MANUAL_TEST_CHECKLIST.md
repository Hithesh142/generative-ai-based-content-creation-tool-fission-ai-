# 📋 Fission AI — Manual Quality Assurance Checklist

This checklist details manual verification protocols to validate layout responsiveness, theme toggling, provider fallbacks, export file integrity, and fragment re-rendering isolation.

---

## 🖥️ 1. Responsive Layout & Design System

- [ ] **Desktop View (>= 1200px):**
  - Verify left sidebar occupies fixed control panel area.
  - Verify Studio displays idea cards in a balanced **2-column responsive grid**.
  - Verify gradient wordmark `FISSION AI` (`#7C5CFF` to `#00D1FF`) renders sharply using Google Font **Sora**.
  - Verify cards have subtle border `#2A2A3D`, 16px radius, and soft shadow with hover lift.
- [ ] **Mobile / Tablet View (< 768px):**
  - Open browser DevTools in responsive device mode (e.g. iPhone 14 Pro, Pixel 7).
  - Verify idea cards collapse automatically to a clean **1-column layout**.
  - Verify touch targets for all action buttons (Generate, Save, Copy, Schedule) are at least 44px in height.
  - Verify font size does not drop below 16px for form inputs to prevent mobile auto-zoom.

---

## 🎨 2. Dark & Light Theme Switching & Persistence

- [ ] **Settings Theme Toggle:**
  - Navigate to the **⚙️ Settings** tab.
  - Select `☀️ Light (Clean Studio)`.
  - Verify the entire workspace transitions to light theme immediately:
    - Page background: `#F7F7FB`
    - Card surfaces: `#FFFFFF`
    - Body text: `#14141F`
    - Muted text: `#5C5C70`
    - Accent gradient buttons: preserved.
- [ ] **Persistence Across Session & Restarts:**
  - Refresh the browser (`F5` or `Ctrl+R`).
  - Verify the studio remains in Light mode without reverting to Dark.
  - Stop the Streamlit server and restart it with `streamlit run frontend/main.py`.
  - Confirm the saved theme preference is loaded directly from the SQLite `app_settings` table.
- [ ] **Switch back to Dark:**
  - Switch back to `🌙 Dark (Modern AI Studio - Default)`.
  - Confirm instant return to dark palette.

---

## ⚡ 3. Studio Strategy Generation & Fragment Isolation

- [ ] **Empty State Illustration:**
  - Open the **🚀 Studio** tab when no ideas have been generated.
  - Verify the friendly empty state SVG/emoji card renders with clear instructions and a call to action.
- [ ] **Generate Strategy Action:**
  - In the left sidebar, enter a topic (e.g. `Minimalist Productivity Workflows`).
  - Click `✨ Generate Strategy`.
  - Verify the loading indicator displays `Writing hooks, angles, and visual concepts for 'Minimalist Productivity Workflows' via Groq...`.
  - Verify a toast notification confirms strategy generation completion.
  - Verify the 4 metric tiles at the top update: Ideas in Studio, Visuals Rendered, Scheduled This Week, Drafts.
- [ ] **Fragment Re-rendering Isolation (`@st.fragment`):**
  - On Idea Card #1, click `🎨 Generate Image`.
  - Observe that only Card #1 undergoes re-rendering and loading shimmer.
  - Verify the rest of the cards, the sidebar, and other tabs do not flash or reset their state.

---

## 🖼️ 4. Visual Composition, Variations & Lightbox

- [ ] **Cloudflare Workers AI Generation:**
  - Ensure `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` are in `.env`.
  - Generate an image; verify rapid generation (< 5 seconds) via FLUX Schnell.
- [ ] **Visual Lightbox Modal (`@st.dialog`):**
  - Click `🔍 View High-Res` or click on the generated thumbnail.
  - Verify the lightbox modal opens displaying full image resolution, model identifier, and resolution metadata.
  - Verify the `⬇️ Download High-Res Visual (PNG)` button within the modal saves the image.
- [ ] **Multiple Visual Variations Grid:**
  - Click `🖼️ 3 Variations` on an idea card.
  - Verify 3 distinct visual compositions are generated and displayed in a 3-column sub-grid.
  - Click `Attach Variation 2`; verify Card #1 updates its active image to the chosen variation.
- [ ] **Smart Provider Fallback:**
  - In sidebar advanced settings, select `Free Engine (FLUX - Public Server)`.
  - Generate an image to verify zero-credential community generation.

---

## 🧰 5. Professional AI Toolkit Operations

- [ ] **Psychological Hook Variants (A/B Testing):**
  - Open `🪝 5 Hook Variants` popover on any idea card.
  - Click `Generate Angles`; verify 5 distinct psychological angles (Curiosity Gap, Contrarian, Problem-Agitation, Data-Driven, Storytelling) are presented with rationales.
  - Click `Apply this Hook` on angle #2; confirm the card's hook callout updates immediately.
- [ ] **Caption Polish & Translation:**
  - Open `✍️ Rewrite Caption` popover.
  - Select `Translate` and pick `Spanish`.
  - Click `Generate Rewrite`; inspect proposed translation; click `Apply Rewrite` and verify card caption updates.
- [ ] **Tiered Hashtag Generator:**
  - Open `🏷️ Tiered Hashtags` popover.
  - Click `Generate Tiers`; verify Niche, Trending, and Branded tiers appear with platform count limits.
  - Click `Apply Deduplicated Tags`.
- [ ] **Content Quality Audit:**
  - Open `📈 Quality Score` popover.
  - Click `Audit Post`; verify 0–100 score breakdown (Hook, Clarity, CTA, Platform Fit) and actionable improvement bullets.

---

## 📅 6. Content Calendar & RFC 5545 .ICS Import

- [ ] **Strategic Content Plan Generator:**
  - In Studio, expand `Strategic Content Plan Generator`.
  - Enter topic `AI for Creative Agencies`, length `7-Day Roadmap`, and click `Generate Strategic Content Plan`.
  - Click `💾 Save All 7 Items into Library & Calendar (1-Click)`.
  - Verify toast confirms all 7 items were scheduled.
- [ ] **Calendar Views:**
  - Navigate to **📅 Calendar** tab.
  - Verify metrics show 7 scheduled items for upcoming dates.
  - Switch between `🗓️ Upcoming Schedule View` and `📊 7-Day Week View`.
  - In Upcoming Schedule View, click `⚙️ Edit Schedule & Status` on any item; update date and change status to `Ready`.
- [ ] **RFC 5545 .ICS Export & Google Calendar Import:**
  - Click `📅 Export as .ICS (Google/Apple/Outlook)` to download `fission_content_calendar.ics`.
  - Open Google Calendar (`calendar.google.com`) -> Settings -> Import & Export -> Select file -> Import.
  - Confirm events appear with scheduled start times, event summary, and full caption in the description.

---

## 📚 7. Library Management & Excel UTF-8 BOM Compatibility

- [ ] **Filter & Search:**
  - Navigate to **📚 Library** tab.
  - Search by keyword in the search bar; verify instant filtering.
  - Filter by platform `LinkedIn` and status `Ready`.
- [ ] **Excel CSV BOM Export:**
  - Under `Export Library Bundle`, click `📊 Export as CSV (Excel BOM)`.
  - Open `fission_content_library.csv` in **Microsoft Excel on Windows**.
  - Verify special characters (emojis, accents, smart quotes) display crisp and clean without UTF-8 garbling (`Ã¢Â€Â™`).
- [ ] **ZIP Archive Export:**
  - Click `📦 Export as ZIP (Images + Text)`.
  - Extract the downloaded `.zip` file; verify directory contains `.txt` caption files, `.png` visuals, and a summary CSV.

---

## 🎨 8. Brand Identity Steering

- [ ] **Create Brand Profile:**
  - Navigate to **🎨 Brand** tab.
  - Create profile `Quantum Tech`: Voice `Authoritative, technical, crisp`, Visual Palette `#00D1FF neon cyan, #7C5CFF violet`, Forbidden words `game-changer, synergy, magic`.
  - Save profile and mark as active.
- [ ] **Prompt Steering Verification:**
  - Return to Studio and generate a strategy.
  - Verify generated captions do not contain any of the forbidden words and follow the technical authoritative tone.
  - Enhance an image prompt; verify `#00D1FF` and `#7C5CFF` visual color grading is injected into the enhanced prompt.
