"""
Fission AI - Professional AI Tools Service
Implements:
1. Content Plan Generator (7-day and 30-day schedules with format diversity)
2. Hook Variants / A-B Testing (5 psychological angles with rationales)
3. Caption Rewriter (shorten, bold, professional, storytelling, translation)
4. Tiered Hashtag Generator (niche, trending, branded tiers with platform limits)
5. Content Quality Scorer (0-100 rubric with heuristic disclaimer)
6. Multi-Platform Content Repurposing
7. Multiple Visual Variations Generation
All tools use Groq with Pydantic validation, retry logic, and brand profile injection.
"""

import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import groq
from pydantic import BaseModel, Field

from config.logging_config import get_logger
from config.settings import GROQ_MODEL, get_groq_api_key
from services.content_generator import _extract_json
from services.image_generator import (
    ImageGenerationResult,
    apply_style_preset,
    generate_image,
)

logger = get_logger("ai_tools")


def _extract_json_from_response(raw_text: str) -> Dict[str, Any]:
    """Helper to extract and decode JSON dict from LLM output."""
    cleaned = _extract_json(raw_text)
    return json.loads(cleaned)


# ============================================================
# BRAND PROFILE FORMATTING HELPER
# ============================================================

def format_brand_guidelines(brand_profile: Optional[Dict[str, Any]]) -> str:
    """Format an active brand profile dictionary into system prompt instructions."""
    if not brand_profile:
        return ""

    lines = ["\n[ACTIVE BRAND IDENTITY & GUIDELINES]"]
    if brand_profile.get("name"):
        lines.append(f"- Brand Name: {brand_profile['name']}")
    if brand_profile.get("voice"):
        lines.append(f"- Brand Voice: {brand_profile['voice']}")
    if brand_profile.get("language"):
        lines.append(f"- Language: {brand_profile['language']}")
    if brand_profile.get("target_market"):
        lines.append(f"- Target Market: {brand_profile['target_market']}")
    if brand_profile.get("audience_age_group"):
        lines.append(f"- Target Age Group: {brand_profile['audience_age_group']}")
    if brand_profile.get("brand_colors"):
        lines.append(f"- Brand Visual Palette: {brand_profile['brand_colors']}")
    if brand_profile.get("business_objective"):
        lines.append(f"- Core Business Objective: {brand_profile['business_objective']}")
    if brand_profile.get("preferred_cta_style"):
        lines.append(f"- Preferred CTA Style: {brand_profile['preferred_cta_style']}")
    if brand_profile.get("words_to_avoid"):
        lines.append(f"- STRICTLY FORBIDDEN WORDS/PHRASES (DO NOT USE): {brand_profile['words_to_avoid']}")

    return "\n".join(lines)


# ============================================================
# 1. CONTENT PLAN GENERATOR (7-Day & 30-Day Plans)
# ============================================================

class ContentPlanItem(BaseModel):
    day: int = Field(..., description="Day number (1, 2, ...)")
    title: str = Field(..., description="Topic or headline for this day")
    platform: str = Field(..., description="Target social platform")
    content_type: str = Field(..., description="Format: Post, Carousel, Short/Reel, Thread, or Article")
    hook: str = Field(..., description="Attention-grabbing opening hook")
    caption: str = Field(..., description="Complete caption or script outline")
    cta: str = Field(..., description="Actionable call to action")
    hashtags: List[str] = Field(default_factory=list, description="Target hashtags")
    visual_concept: str = Field(default="", description="Visual or thumbnail idea")
    image_prompt: str = Field(default="", description="Detailed AI image generation prompt")


class ContentPlanResponse(BaseModel):
    topic: str
    duration_days: int
    strategy_summary: str
    plan: List[ContentPlanItem]


def generate_content_plan(
    topic: str,
    duration_days: int = 7,
    platform: Optional[str] = None,
    start_date: Optional[str] = None,
    brand_profile: Optional[Dict[str, Any]] = None,
    client: Optional[groq.Groq] = None,
) -> ContentPlanResponse:
    """
    Generate a 7-day or 30-day comprehensive content calendar strategy with diverse formats.
    """
    if duration_days not in (7, 30):
        duration_days = 7

    target_platform = platform or "Multi-Platform"
    brand_context = format_brand_guidelines(brand_profile)

    system_prompt = (
        f"You are an elite Content Strategy Director.\n"
        f"Generate a structured {duration_days}-day editorial content calendar for the topic '{topic}'.\n"
        f"Target Platform(s): {target_platform}.\n"
        f"Requirements:\n"
        f"1. Generate exactly {duration_days} distinct, non-repetitive days of content.\n"
        f"2. Ensure healthy format rotation (e.g. Post, Carousel, Reel/Short, Thread, Article).\n"
        f"3. Craft compelling hooks, complete captions, clear CTAs, and descriptive image prompts.\n"
        f"{brand_context}\n\n"
        f"You MUST output ONLY a valid JSON object matching this schema:\n"
        f"{{\n"
        f'  "topic": "{topic}",\n'
        f'  "duration_days": {duration_days},\n'
        f'  "strategy_summary": "1-2 sentence executive overview of the calendar narrative",\n'
        f'  "plan": [\n'
        f"    {{\n"
        f'      "day": 1,\n'
        f'      "title": "Clear actionable title",\n'
        f'      "platform": "{target_platform}",\n'
        f'      "content_type": "Format",\n'
        f'      "hook": "Strong opening hook",\n'
        f'      "caption": "Full informative caption",\n'
        f'      "cta": "Call to action",\n'
        f'      "hashtags": ["#tag1", "#tag2"],\n'
        f'      "visual_concept": "Creative visual description",\n'
        f'      "image_prompt": "Photorealistic 8k visual prompt"\n'
        f"    }}\n"
        f"  ]\n"
        f"}}"
    )

    user_prompt = f"Create the {duration_days}-day editorial calendar for topic: {topic}"

    if client is None:
        api_key = get_groq_api_key()
        client = groq.Groq(api_key=api_key)

    raw_response = None
    for attempt in range(2):
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt if attempt == 0 else f"{user_prompt} - ensure strict JSON syntax."},
                ],
                model=GROQ_MODEL,
                temperature=0.6,
                max_tokens=4000 if duration_days == 30 else 2500,
                response_format={"type": "json_object"},
            )
            raw_response = chat_completion.choices[0].message.content or ""
            data = _extract_json_from_response(raw_response)
            return ContentPlanResponse(**data)
        except Exception as e:
            logger.warning(f"Content plan generation attempt {attempt + 1} failed: {e}")
            if attempt == 1:
                # Fallback generator
                fallback_items = []
                for d in range(1, duration_days + 1):
                    fallback_items.append(
                        ContentPlanItem(
                            day=d,
                            title=f"{topic} Strategy - Day {d}",
                            platform=target_platform,
                            content_type="Post" if d % 2 == 0 else "Carousel",
                            hook=f"Day {d} key insight on {topic} you should know.",
                            caption=f"Insightful actionable breakdown regarding {topic} for day {d}.",
                            cta="Save this post for your reference!",
                            hashtags=[f"#{re.sub(r'[^a-zA-Z0-9]', '', topic).lower()}", "#strategy"],
                            visual_concept=f"Visual representation of {topic} concept {d}",
                            image_prompt=f"Modern editorial visual representing {topic}, photorealistic 8k",
                        )
                    )
                return ContentPlanResponse(
                    topic=topic,
                    duration_days=duration_days,
                    strategy_summary=f"Automated {duration_days}-day strategic content roadmap for {topic}.",
                    plan=fallback_items,
                )


# ============================================================
# 2. HOOK VARIANTS / A-B TESTING (5 Psychological Angles)
# ============================================================

class HookVariant(BaseModel):
    angle: str = Field(..., description="Psychological angle (e.g. Curiosity Gap, Contrarian)")
    hook: str = Field(..., description="The alternative headline or hook copy")
    rationale: str = Field(..., description="Why this hook works and when to test it")


class HookVariantsResponse(BaseModel):
    variants: List[HookVariant]


def generate_hook_variants(
    idea: Dict[str, Any],
    brand_profile: Optional[Dict[str, Any]] = None,
    client: Optional[groq.Groq] = None,
) -> HookVariantsResponse:
    """
    Generate 5 distinct psychological hook variants for A/B testing:
    1. Curiosity Gap / Mystery
    2. Contrarian / Bold Hot-Take
    3. Problem-Agitation / Pain-Point
    4. Data / Statistical / Case Study
    5. Direct Transformation / Value Promise
    """
    title = idea.get("title", "")
    current_hook = idea.get("hook", "")
    caption = idea.get("caption", "")
    platform = idea.get("platform", "Social Media")
    brand_context = format_brand_guidelines(brand_profile)

    system_prompt = (
        f"You are a master direct-response copywriter.\n"
        f"Generate exactly 5 high-converting alternative opening hooks for the given content idea on {platform}.\n"
        f"Use these 5 distinct psychological angles:\n"
        f"1. Curiosity Gap (Intrigue without clickbait)\n"
        f"2. Contrarian / Bold Hot-Take (Challenges common wisdom)\n"
        f"3. Problem-Agitation (Hits a resonant pain point)\n"
        f"4. Data / Case Study Proof (Authoritative proof)\n"
        f"5. Direct Transformation / Fast Value (Clear immediate benefit)\n"
        f"{brand_context}\n\n"
        f"Output ONLY a JSON object with this exact structure:\n"
        f"{{\n"
        f'  "variants": [\n'
        f'    {{"angle": "Curiosity Gap", "hook": "...", "rationale": "..."}},\n'
        f'    {{"angle": "Contrarian / Hot Take", "hook": "...", "rationale": "..."}},\n'
        f'    {{"angle": "Problem-Agitation", "hook": "...", "rationale": "..."}},\n'
        f'    {{"angle": "Data / Proof", "hook": "...", "rationale": "..."}},\n'
        f'    {{"angle": "Direct Transformation", "hook": "...", "rationale": "..."}}\n'
        f"  ]\n"
        f"}}"
    )

    user_content = (
        f"Content Title: {title}\n"
        f"Current Hook: {current_hook}\n"
        f"Caption Summary: {caption[:250]}"
    )

    if client is None:
        api_key = get_groq_api_key()
        client = groq.Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            model=GROQ_MODEL,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content or ""
        data = _extract_json_from_response(raw_text)
        return HookVariantsResponse(**data)
    except Exception as err:
        logger.warning(f"Hook variants generation error: {err}")
        return HookVariantsResponse(
            variants=[
                HookVariant(angle="Curiosity Gap", hook=f"The one thing about {title} nobody talks about.", rationale="Creates an open loop in reader mind."),
                HookVariant(angle="Contrarian", hook=f"Most advice on {title} is completely backwards.", rationale="Disrupts expectations with a bold challenge."),
                HookVariant(angle="Problem-Agitation", hook=f"Still struggling with {title}? Here is why.", rationale="Addresses visceral frustration directly."),
                HookVariant(angle="Data / Proof", hook=f"How doing this single tweak changed {title} results by 80%.", rationale="Provides tangible perceived authority."),
                HookVariant(angle="Direct Transformation", hook=f"How to master {title} in 3 actionable steps.", rationale="Promises fast, friction-free value."),
            ]
        )


# ============================================================
# 3. CAPTION REWRITER (Shorten, Bold, Professional, Translate)
# ============================================================

class CaptionRewriteResponse(BaseModel):
    original_caption: str
    rewritten_caption: str
    style: str
    language: str = "English"
    changes_summary: str


def rewrite_caption(
    caption: str,
    style: str = "bold",
    target_language: Optional[str] = None,
    brand_profile: Optional[Dict[str, Any]] = None,
    client: Optional[groq.Groq] = None,
) -> CaptionRewriteResponse:
    """
    Rewrite a caption according to selected style preset or target language:
    - shorten (concise, high impact punchiness)
    - bold (provocative, confident, persuasive)
    - professional (polished, authoritative, executive)
    - storytelling (narrative, relatable, immersive)
    - translate (fluent native translation)
    """
    style_key = style.lower().strip()
    lang = target_language or (brand_profile.get("language") if brand_profile else "English") or "English"
    brand_context = format_brand_guidelines(brand_profile)

    style_instructions = {
        "shorten": "Make this caption 40-50% more concise. Cut fluff and keep only punchy, high-impact statements.",
        "bold": "Rewrite this caption to be unapologetically bold, highly opinionated, and commanding.",
        "professional": "Rewrite this caption in an authoritative, executive, LinkedIn-thought-leader professional tone.",
        "storytelling": "Rewrite this caption as an engaging narrative story with emotional resonance and a lesson.",
        "translate": f"Translate and culturally adapt this caption into fluent, native {lang}.",
    }
    instruction = style_instructions.get(style_key, f"Rewrite in a {style} manner in {lang}.")

    system_prompt = (
        f"You are an expert social media copy editor.\n"
        f"Goal: {instruction}\n"
        f"Target Language: {lang}\n"
        f"{brand_context}\n\n"
        f"Output ONLY a JSON object with this exact structure:\n"
        f"{{\n"
        f'  "original_caption": "{caption[:50]}...",\n'
        f'  "rewritten_caption": "full rewritten text here",\n'
        f'  "style": "{style}",\n'
        f'  "language": "{lang}",\n'
        f'  "changes_summary": "1 sentence describing key edits"\n'
        f"}}"
    )

    if client is None:
        api_key = get_groq_api_key()
        client = groq.Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Original Caption:\n{caption}"},
            ],
            model=GROQ_MODEL,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content or ""
        data = _extract_json_from_response(raw_text)
        data["original_caption"] = caption
        return CaptionRewriteResponse(**data)
    except Exception as err:
        logger.warning(f"Caption rewrite error: {err}")
        return CaptionRewriteResponse(
            original_caption=caption,
            rewritten_caption=caption,
            style=style,
            language=lang,
            changes_summary=f"Fallback: returned original text due to: {err}",
        )


# ============================================================
# 4. TIERED HASHTAG GENERATOR (Niche + Trending + Branded)
# ============================================================

PLATFORM_HASHTAG_LIMITS = {
    "instagram": 15,
    "linkedin": 5,
    "twitter": 3,
    "tiktok": 6,
    "youtube": 4,
    "general": 8,
}


class HashtagTiersResponse(BaseModel):
    platform: str
    niche_hashtags: List[str]
    trending_hashtags: List[str]
    branded_hashtags: List[str]
    all_hashtags: List[str]
    platform_limit: int


def generate_hashtags(
    topic: str,
    platform: str = "Instagram",
    keywords: Optional[List[str]] = None,
    brand_profile: Optional[Dict[str, Any]] = None,
    client: Optional[groq.Groq] = None,
) -> HashtagTiersResponse:
    """
    Generate tiered, deduplicated hashtags with platform-appropriate count limits:
    - Niche (specific target community)
    - Trending (broad discovery)
    - Branded (custom topic/brand alignment)
    """
    platform_key = platform.lower().split()[0].replace("/", "")
    limit = PLATFORM_HASHTAG_LIMITS.get(platform_key, 8)
    brand_name = brand_profile.get("name") if brand_profile else None

    system_prompt = (
        f"You are a social media hashtag researcher.\n"
        f"Generate optimized hashtags for topic '{topic}' on {platform}.\n"
        f"Provide 3 tiers:\n"
        f"1. Niche: highly relevant community tags (3-6)\n"
        f"2. Trending: popular discovery tags (3-6)\n"
        f"3. Branded: unique tags for '{brand_name or topic}' (2-3)\n"
        f"Ensure every tag starts with #. Do NOT repeat tags across tiers.\n\n"
        f"Output ONLY a JSON object:\n"
        f"{{\n"
        f'  "niche_hashtags": ["#tag1", "#tag2"],\n'
        f'  "trending_hashtags": ["#tag3", "#tag4"],\n'
        f'  "branded_hashtags": ["#tag5"]\n'
        f"}}"
    )

    if client is None:
        api_key = get_groq_api_key()
        client = groq.Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Topic: {topic}, Keywords: {keywords or []}"},
            ],
            model=GROQ_MODEL,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content or ""
        data = _extract_json_from_response(raw_text)

        raw_niche = [h.strip() if h.startswith("#") else f"#{h.strip()}" for h in data.get("niche_hashtags", []) if h.strip()]
        raw_trend = [h.strip() if h.startswith("#") else f"#{h.strip()}" for h in data.get("trending_hashtags", []) if h.strip()]
        raw_brand = [h.strip() if h.startswith("#") else f"#{h.strip()}" for h in data.get("branded_hashtags", []) if h.strip()]

        # Deduplicate while preserving order
        seen = set()
        deduped: List[str] = []
        for tag in raw_niche + raw_trend + raw_brand:
            tag_clean = tag.lower()
            if tag_clean not in seen:
                seen.add(tag_clean)
                deduped.append(tag)

        # Enforce platform limit
        final_list = deduped[:limit]

        return HashtagTiersResponse(
            platform=platform,
            niche_hashtags=raw_niche,
            trending_hashtags=raw_trend,
            branded_hashtags=raw_brand,
            all_hashtags=final_list,
            platform_limit=limit,
        )
    except Exception as err:
        logger.warning(f"Hashtag generation error: {err}")
        topic_slug = re.sub(r"[^a-zA-Z0-9]", "", topic).lower()
        fallback_tags = [f"#{topic_slug}", f"#{topic_slug}tips", "#contentcreator", "#growth"][:limit]
        return HashtagTiersResponse(
            platform=platform,
            niche_hashtags=[f"#{topic_slug}"],
            trending_hashtags=["#contentcreator"],
            branded_hashtags=[f"#{topic_slug}tips"],
            all_hashtags=fallback_tags,
            platform_limit=limit,
        )


# ============================================================
# 5. CONTENT QUALITY SCORE (0-100 Heuristic Evaluation)
# ============================================================

class ContentQualityResponse(BaseModel):
    overall_score: int = Field(..., description="Overall score 0-100")
    hook_strength: int = Field(..., description="0-100 hook rating")
    clarity_and_readability: int = Field(..., description="0-100 clarity rating")
    cta_effectiveness: int = Field(..., description="0-100 call to action rating")
    platform_fit: int = Field(..., description="0-100 platform fit rating")
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    actionable_suggestions: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "AI Quality Estimate: Heuristic content analysis for strategic optimization, "
        "not an empirical performance guarantee."
    )


def evaluate_content_quality(
    item: Dict[str, Any],
    brand_profile: Optional[Dict[str, Any]] = None,
    client: Optional[groq.Groq] = None,
) -> ContentQualityResponse:
    """
    Evaluate content quality on a 0-100 scale across 4 core dimensions:
    - Hook strength
    - Clarity & readability
    - CTA effectiveness
    - Platform fit
    Provides specific strengths, weaknesses, and improvement steps.
    """
    title = item.get("title", "")
    platform = item.get("platform", "General")
    hook = item.get("hook", "")
    caption = item.get("caption", "")
    cta = item.get("cta", "")
    brand_context = format_brand_guidelines(brand_profile)

    system_prompt = (
        f"You are a senior social media content auditor.\n"
        f"Evaluate the provided content post for {platform}.\n"
        f"Score each category strictly from 0 to 100 based on modern engagement best practices.\n"
        f"{brand_context}\n\n"
        f"Output ONLY a JSON object:\n"
        f"{{\n"
        f'  "overall_score": 82,\n'
        f'  "hook_strength": 85,\n'
        f'  "clarity_and_readability": 90,\n'
        f'  "cta_effectiveness": 75,\n'
        f'  "platform_fit": 80,\n'
        f'  "strengths": ["...", "..."],\n'
        f'  "weaknesses": ["..."],\n'
        f'  "actionable_suggestions": ["...", "..."]\n'
        f"}}"
    )

    user_text = (
        f"Title: {title}\n"
        f"Platform: {platform}\n"
        f"Hook: {hook}\n"
        f"Caption: {caption}\n"
        f"CTA: {cta}"
    )

    if client is None:
        api_key = get_groq_api_key()
        client = groq.Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            model=GROQ_MODEL,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content or ""
        data = _extract_json_from_response(raw_text)
        return ContentQualityResponse(**data)
    except Exception as err:
        logger.warning(f"Quality score evaluation error: {err}")
        return ContentQualityResponse(
            overall_score=75,
            hook_strength=75,
            clarity_and_readability=80,
            cta_effectiveness=70,
            platform_fit=75,
            strengths=["Clear topic focus", "Cohesive structure"],
            weaknesses=["Could sharpen hook urgency"],
            actionable_suggestions=["Test adding a stronger curiosity angle to the hook"],
        )


# ============================================================
# 6. CONTENT REPURPOSING (Multi-Platform Adaptation)
# ============================================================

class RepurposedIdea(BaseModel):
    platform: str
    content_type: str
    title: str
    hook: str
    caption: str
    cta: str
    hashtags: List[str]
    visual_concept: str
    image_prompt: str


class RepurposeResponse(BaseModel):
    original_title: str
    repurposed_ideas: List[RepurposedIdea]


def repurpose_content(
    item: Dict[str, Any],
    target_platforms: List[str],
    brand_profile: Optional[Dict[str, Any]] = None,
    client: Optional[groq.Groq] = None,
) -> RepurposeResponse:
    """
    Adapt a single content concept into native formats for multiple target platforms
    (e.g., adapt an Instagram Carousel into a LinkedIn Article and a Twitter/X Thread).
    """
    title = item.get("title", "")
    caption = item.get("caption", "")
    hook = item.get("hook", "")
    source_platform = item.get("platform", "Original")
    brand_context = format_brand_guidelines(brand_profile)

    platforms_str = ", ".join(target_platforms)

    system_prompt = (
        f"You are a cross-platform content repurposing specialist.\n"
        f"Adapt this content from {source_platform} into native formats for: {platforms_str}.\n"
        f"Rules:\n"
        f"- For LinkedIn: Professional tone, line breaks for readability, industry insights.\n"
        f"- For Twitter/X: Punchy tweet thread with numbered points and minimal hashtags.\n"
        f"- For TikTok/YouTube Shorts: Conversational spoken script with on-screen visual cues.\n"
        f"- For Instagram: Visual-first copy with aesthetic image prompts.\n"
        f"{brand_context}\n\n"
        f"Output ONLY a JSON object:\n"
        f"{{\n"
        f'  "original_title": "{title}",\n'
        f'  "repurposed_ideas": [\n'
        f"    {{\n"
        f'      "platform": "LinkedIn",\n'
        f'      "content_type": "Article",\n'
        f'      "title": "...",\n'
        f'      "hook": "...",\n'
        f'      "caption": "...",\n'
        f'      "cta": "...",\n'
        f'      "hashtags": ["#tag1", "#tag2"],\n'
        f'      "visual_concept": "...",\n'
        f'      "image_prompt": "..."\n'
        f"    }}\n"
        f"  ]\n"
        f"}}"
    )

    user_text = f"Source Title: {title}\nSource Hook: {hook}\nSource Caption:\n{caption}"

    if client is None:
        api_key = get_groq_api_key()
        client = groq.Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            model=GROQ_MODEL,
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content or ""
        data = _extract_json_from_response(raw_text)
        return RepurposeResponse(**data)
    except Exception as err:
        logger.warning(f"Repurposing error: {err}")
        fallback_ideas = []
        for p in target_platforms:
            fallback_ideas.append(
                RepurposedIdea(
                    platform=p,
                    content_type="Post",
                    title=f"{title} ({p} Edition)",
                    hook=hook,
                    caption=caption,
                    cta="Follow for more insights!",
                    hashtags=["#content", f"#{p.lower().replace(' ', '')}"],
                    visual_concept=f"Visual adaptation for {p}",
                    image_prompt=f"Modern editorial graphic for {p}, photorealistic 8k",
                )
            )
        return RepurposeResponse(original_title=title, repurposed_ideas=fallback_ideas)


# ============================================================
# 7. MULTIPLE VISUAL VARIATIONS GENERATOR
# ============================================================

def generate_visual_variations(
    prompt: str,
    style: str = "photorealistic",
    aspect_ratio: str = "1:1",
    num_variations: int = 3,
    provider: str = "auto",
    brand_profile: Optional[Dict[str, Any]] = None,
) -> List[ImageGenerationResult]:
    """
    Generate 2-4 distinct visual variations for a given prompt by applying
    subtle composition, lighting, and palette modifiers.
    """
    count = max(2, min(4, num_variations))
    variation_modifiers = [
        "cinematic lighting, eye-level perspective, centered composition",
        "dramatic side lighting, dynamic low-angle perspective, atmospheric depth",
        "soft natural studio lighting, high key elegance, crisp detailed focus",
        "golden hour warm ambient lighting, wide angle composition, vivid color contrast",
    ]

    brand_color_mod = ""
    if brand_profile and brand_profile.get("brand_colors"):
        brand_color_mod = f", color harmony inspired by {brand_profile['brand_colors']}"

    results: List[ImageGenerationResult] = []

    for idx in range(count):
        modifier = variation_modifiers[idx % len(variation_modifiers)]
        varied_prompt = f"{prompt.strip()}{brand_color_mod}, {modifier}"

        try:
            res = generate_image(
                prompt=varied_prompt,
                style=style,
                aspect_ratio=aspect_ratio,
                provider=provider,
            )
            results.append(res)
        except Exception as img_err:
            logger.warning(f"Variation {idx + 1} generation failed: {img_err}")
            results.append(
                ImageGenerationResult(
                    prompt=varied_prompt,
                    style=style,
                    aspect_ratio=aspect_ratio,
                    error=str(img_err),
                    is_success=False,
                )
            )

    return results
