"""
Fission AI - Modular Idea Card Component
Renders individual strategy cards inside @st.fragment for isolated re-rendering.
Includes:
- Platform icon badge, format chip, status pill (text + icon)
- Title & highlighted hook callout (accent left border)
- Collapsible caption and hashtags
- CSS-only skeleton shimmer placeholder before generation
- Real image rendering with @st.dialog lightbox viewer
- Action row: Generate (primary filled), Save, Copy, Download, Schedule, AI Toolkit
"""

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from database.db import create_item, update_item, update_schedule
from services.ai_tools import (
    evaluate_content_quality,
    generate_hashtags,
    generate_hook_variants,
    generate_visual_variations,
    repurpose_content,
    rewrite_caption,
)
from services.image_generator import (
    ASPECT_RATIO_MAP,
    STYLE_PRESETS,
    enhance_image_prompt,
    generate_image,
)


@st.dialog("🖼️ Visual Lightbox")
def _open_image_lightbox(
    image_path: str,
    title: str,
    model_used: str,
    width: int,
    height: int,
    style: str,
) -> None:
    """Lightbox modal viewer for high-resolution inspection."""
    st.image(image_path, use_container_width=True)
    st.caption(f"**Concept:** {title} | **Model:** {model_used} | **Resolution:** {width}x{height} | **Style:** {style}")
    path_obj = Path(image_path)
    if path_obj.exists():
        with open(path_obj, "rb") as f_img:
            st.download_button(
                label="⬇️ Download High-Res Visual (PNG)",
                data=f_img,
                file_name=path_obj.name,
                mime="image/png",
                use_container_width=True
            )


@st.fragment
def render_idea_card(
    index: int,
    idea: Dict[str, Any],
    gen_id: str,
    topic: str,
    platform: str,
    audience: str,
    active_brand: Optional[Dict[str, Any]] = None,
    image_engine: str = "Cloudflare Workers AI",
) -> None:
    """Render a single interactive content card isolated inside a Streamlit fragment."""
    title = idea.get("title", f"Content Idea {index}")
    c_type = idea.get("content_type", "Post")

    # State keys scoped to this card & generation
    hook_key = f"card_hook_{gen_id}_{index}"
    if hook_key not in st.session_state:
        st.session_state[hook_key] = idea.get("hook", "No hook provided.")

    caption_key = f"card_caption_{gen_id}_{index}"
    if caption_key not in st.session_state:
        st.session_state[caption_key] = idea.get("caption", "No caption generated.")

    hashtags_key = f"card_hashtags_{gen_id}_{index}"
    if hashtags_key not in st.session_state:
        st.session_state[hashtags_key] = idea.get("hashtags", [])

    prompt_key = f"card_prompt_{gen_id}_{index}"
    if prompt_key not in st.session_state:
        st.session_state[prompt_key] = idea.get("image_prompt", "")

    saved_flag_key = f"card_saved_{gen_id}_{index}"

    # Platform icons mapping
    platform_icons = {
        "instagram": "📸 Instagram",
        "linkedin": "💼 LinkedIn",
        "twitter": "🐦 Twitter / X",
        "youtube": "▶️ YouTube",
        "tiktok": "🎵 TikTok",
        "blog": "📝 Blog Post",
        "newsletter": "📬 Newsletter",
    }
    plat_lower = platform.lower()
    plat_badge = next((v for k, v in platform_icons.items() if k in plat_lower), f"🌐 {platform}")

    with st.container(border=True):
        # Header Badge Strip
        h_col1, h_col2 = st.columns([3, 2])
        with h_col1:
            st.markdown(
                f"""
                <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px;">
                    <span class="fiss-chip">{plat_badge}</span>
                    <span class="fiss-chip">🏷️ {c_type}</span>
                    <span class="fiss-chip fiss-chip-status-draft">🟡 Draft</span>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.subheader(f"{index}. {title}")
        with h_col2:
            st.caption(f"**Target:** {idea.get('target_audience', audience or 'General')} | **Duration:** {idea.get('duration_estimate', 'N/A')}")

        # Highlighted Hook Callout (accent left border)
        current_hook = st.session_state[hook_key]
        st.markdown(f'<div class="hook-callout">🎯 <b>Hook:</b> {current_hook}</div>', unsafe_allow_html=True)

        # Collapsible Caption & Copy Box
        with st.expander("✍️ Read Caption & #️⃣ Hashtags", expanded=False):
            st.markdown(st.session_state[caption_key])
            st.caption(f"**Call to Action:** {idea.get('call_to_action', '')}")
            raw_ht = st.session_state[hashtags_key]
            ht_str = " ".join(raw_ht) if isinstance(raw_ht, list) else str(raw_ht or "")
            st.markdown(f"**Hashtags:** `{ht_str}`")

            # Quick Copy Box
            st.caption("📋 Quick Copy:")
            c_copy1, c_copy2 = st.columns(2)
            with c_copy1:
                st.code(st.session_state[caption_key], language=None)
            with c_copy2:
                st.code(ht_str, language=None)

        # Image Generation & Display Area
        st.markdown("#### 🖼️ Visual Composition")
        user_prompt = st.text_area(
            "Image Prompt (editable)",
            key=prompt_key,
            height=75,
            help="Tweak visual prompt before rendering."
        )

        # Engine controls
        c_style, c_aspect = st.columns(2)
        with c_style:
            sel_style = st.selectbox("Style Preset", list(STYLE_PRESETS.keys()), index=0, key=f"c_style_{gen_id}_{index}")
        with c_aspect:
            sel_aspect = st.selectbox("Aspect Ratio", list(ASPECT_RATIO_MAP.keys()), index=0, key=f"c_aspect_{gen_id}_{index}")

        provider_code = (
            "cloudflare" if "Cloudflare" in image_engine
            else "gemini" if "Google Imagen 3" in image_engine
            else "free" if "Free Engine" in image_engine
            else "hf" if "Paid Inference Credits" in image_engine
            else "auto"
        )

        cache_key = f"card_img_{gen_id}_{index}_{hash((user_prompt.strip(), sel_style, sel_aspect, provider_code))}"
        cached_result = st.session_state.image_cache.get(cache_key)

        # Image or Skeleton Shimmer Placeholder
        if cached_result and cached_result.is_success and cached_result.image_path and Path(cached_result.image_path).exists():
            st.image(
                cached_result.image_path,
                caption=f"Engine: {cached_result.model_used} | {cached_result.width}x{cached_result.height}",
                use_container_width=True
            )
            # Lightbox Enlarge Button
            if st.button("🔍 Enlarge Visual (Lightbox)", key=f"lb_btn_{gen_id}_{index}", use_container_width=True):
                _open_image_lightbox(
                    cached_result.image_path,
                    title,
                    cached_result.model_used or "FLUX",
                    cached_result.width,
                    cached_result.height,
                    cached_result.style
                )
        else:
            # Pure CSS Skeleton Shimmer Placeholder
            st.markdown(
                """
                <div class="skeleton-placeholder">
                    <div style="font-size: 32px;">🎨</div>
                    <div style="font-weight: 600;">Visual Not Generated Yet</div>
                    <div style="font-size: 12px; opacity: 0.75;">Click '🎨 Generate Visual' below</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        if cached_result and not cached_result.is_success:
            st.error(cached_result.error or "Image generation failed.")

        # =====================================================
        # CARD ACTION ROW (Filled Primary + Ghost Secondary)
        # =====================================================
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        act_col1, act_col2, act_col3, act_col4, act_col5 = st.columns([3, 2, 2, 2, 2])

        # 1. Primary Generate Action
        with act_col1:
            is_rendered = bool(cached_result and cached_result.is_success)
            btn_label = "🎨 Generate Visual" if not is_rendered else "🔄 Regenerate"
            if st.button(btn_label, key=f"act_gen_{gen_id}_{index}", type="primary", use_container_width=True):
                with st.spinner("Rendering image via Cloudflare / FLUX..."):
                    res = generate_image(
                        prompt=user_prompt,
                        style=sel_style,
                        aspect_ratio=sel_aspect,
                        provider=provider_code
                    )
                    st.session_state.image_cache[cache_key] = res
                    st.rerun()

        # 2. Save to Library
        with act_col2:
            is_saved = saved_flag_key in st.session_state
            save_lbl = "💾 Saved" if is_saved else "💾 Save"
            if st.button(save_lbl, key=f"act_save_{gen_id}_{index}", use_container_width=True):
                item_payload = {
                    "topic": topic,
                    "title": title,
                    "platform": platform,
                    "target_audience": idea.get("target_audience", audience),
                    "content_type": c_type,
                    "hook": st.session_state[hook_key],
                    "caption": st.session_state[caption_key],
                    "cta": idea.get("call_to_action", ""),
                    "hashtags": st.session_state[hashtags_key],
                    "visual_concept": idea.get("visual_concept", ""),
                    "image_prompt": user_prompt,
                    "image_path": cached_result.image_path if (cached_result and cached_result.is_success) else None,
                    "status": "Draft",
                }
                new_id = create_item(item_payload)
                st.session_state[saved_flag_key] = new_id
                st.toast("✅ Saved to Library!", icon="📚")
                st.rerun()

        # 3. Schedule Action Popover
        with act_col3:
            with st.popover("📅 Schedule", use_container_width=True):
                st.markdown("**Add to Editorial Calendar**")
                sched_d = st.date_input("Date", value=datetime.date.today(), key=f"sc_d_{gen_id}_{index}")
                sched_t = st.text_input("Time", value="10:00", key=f"sc_t_{gen_id}_{index}")
                if st.button("Confirm Schedule", key=f"sc_btn_{gen_id}_{index}", type="primary", use_container_width=True):
                    # Save item with scheduled date
                    sched_payload = {
                        "topic": topic,
                        "title": title,
                        "platform": platform,
                        "target_audience": idea.get("target_audience", audience),
                        "content_type": c_type,
                        "hook": st.session_state[hook_key],
                        "caption": st.session_state[caption_key],
                        "cta": idea.get("call_to_action", ""),
                        "hashtags": st.session_state[hashtags_key],
                        "visual_concept": idea.get("visual_concept", ""),
                        "image_prompt": user_prompt,
                        "image_path": cached_result.image_path if (cached_result and cached_result.is_success) else None,
                        "scheduled_date": sched_d.isoformat(),
                        "scheduled_time": sched_t.strip(),
                        "status": "Planned",
                    }
                    create_item(sched_payload)
                    st.toast("✅ Added to Editorial Calendar!", icon="📅")
                    st.rerun()

        # 4. Download Action
        with act_col4:
            if cached_result and cached_result.is_success and cached_result.image_path and Path(cached_result.image_path).exists():
                with open(cached_result.image_path, "rb") as dl_file:
                    st.download_button(
                        label="⬇️ PNG",
                        data=dl_file,
                        file_name=Path(cached_result.image_path).name,
                        mime="image/png",
                        key=f"act_dl_{gen_id}_{index}",
                        use_container_width=True
                    )
            else:
                st.button("⬇️ PNG", disabled=True, key=f"act_dl_dis_{gen_id}_{index}", use_container_width=True)

        # 5. Professional AI Toolkit Popover
        with act_col5:
            with st.popover("⚡ AI Tools", use_container_width=True):
                st.markdown("**Professional AI Feature Suite**")

                # Tool 1: Hook Variants
                with st.expander("🪝 5 Hook Variants (A/B Testing)", expanded=False):
                    if st.button("Generate Angles", key=f"h_btn_{gen_id}_{index}"):
                        with st.spinner("Generating 5 psychological angles..."):
                            h_res = generate_hook_variants(
                                {"title": title, "hook": st.session_state[hook_key], "caption": st.session_state[caption_key], "platform": platform},
                                brand_profile=active_brand
                            )
                            st.session_state[f"h_var_{gen_id}_{index}"] = h_res.variants

                    if f"h_var_{gen_id}_{index}" in st.session_state:
                        for hv in st.session_state[f"h_var_{gen_id}_{index}"]:
                            st.markdown(f"**{hv.angle}:** {hv.hook}")
                            st.caption(f"_{hv.rationale}_")
                            if st.button("Apply", key=f"aph_{gen_id}_{index}_{hash(hv.hook)}"):
                                st.session_state[hook_key] = hv.hook
                                st.toast("Hook updated!", icon="🪝")
                                st.rerun()

                # Tool 2: Caption Rewriter
                with st.expander("✍️ Rewrite Caption", expanded=False):
                    r_style = st.selectbox("Style", ["Shorten", "Bold", "Professional", "Storytelling", "Translate"], key=f"rs_{gen_id}_{index}")
                    r_lang = None
                    if r_style == "Translate":
                        r_lang = st.selectbox("Language", ["Spanish", "French", "German", "Hindi", "Japanese"], key=f"rl_{gen_id}_{index}")
                    if st.button("Rewrite", key=f"rw_btn_{gen_id}_{index}"):
                        with st.spinner("Polishing caption..."):
                            rw_res = rewrite_caption(st.session_state[caption_key], style=r_style, target_language=r_lang, brand_profile=active_brand)
                            st.session_state[caption_key] = rw_res.rewritten_caption
                            st.toast("Caption rewritten and applied!", icon="✍️")
                            st.rerun()

                # Tool 3: Tiered Hashtag Generator
                with st.expander("🏷️ Tiered Hashtags", expanded=False):
                    if st.button("Generate Hashtag Tiers", key=f"ht_btn_{gen_id}_{index}"):
                        with st.spinner("Researching hashtags..."):
                            ht_res = generate_hashtags(topic, platform=platform, brand_profile=active_brand)
                            st.session_state[hashtags_key] = ht_res.all_hashtags
                            st.toast(f"Generated {len(ht_res.all_hashtags)} deduplicated tags!", icon="🏷️")
                            st.rerun()

                # Tool 4: Content Quality Score
                with st.expander("📈 Content Quality Score", expanded=False):
                    if st.button("Audit Post", key=f"q_btn_{gen_id}_{index}"):
                        with st.spinner("Evaluating hook & clarity..."):
                            q_res = evaluate_content_quality(
                                {"title": title, "platform": platform, "hook": st.session_state[hook_key], "caption": st.session_state[caption_key]},
                                brand_profile=active_brand
                            )
                            st.session_state[f"q_res_{gen_id}_{index}"] = q_res

                    if f"q_res_{gen_id}_{index}" in st.session_state:
                        qr = st.session_state[f"q_res_{gen_id}_{index}"]
                        st.metric("Score", f"{qr.overall_score}/100")
                        st.caption(f"Hook: {qr.hook_strength}/100 | Clarity: {qr.clarity_and_readability}/100")
                        for s in qr.actionable_suggestions[:2]:
                            st.markdown(f"• {s}")
                        st.caption(f"_{qr.disclaimer}_")

                # Tool 5: Visual Variations (3 grid)
                with st.expander("🖼️ 3 Visual Variations", expanded=False):
                    if st.button("Render 3 Variations", key=f"var_btn_{gen_id}_{index}"):
                        with st.spinner("Generating 3 compositions..."):
                            var_res = generate_visual_variations(
                                prompt=user_prompt,
                                style=sel_style,
                                aspect_ratio=sel_aspect,
                                num_variations=3,
                                provider=provider_code,
                                brand_profile=active_brand
                            )
                            st.session_state[f"vars_{gen_id}_{index}"] = var_res

                    if f"vars_{gen_id}_{index}" in st.session_state:
                        for v_i, v_obj in enumerate(st.session_state[f"vars_{gen_id}_{index}"]):
                            if v_obj.is_success and v_obj.image_path:
                                st.image(v_obj.image_path, use_container_width=True)
                                if st.button(f"Attach #{v_i+1}", key=f"att_v_{gen_id}_{index}_{v_i}"):
                                    st.session_state.image_cache[cache_key] = v_obj
                                    del st.session_state[f"vars_{gen_id}_{index}"]
                                    st.toast("Attached visual!", icon="🎨")
                                    st.rerun()
