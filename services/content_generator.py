"""
Fission AI - Groq Content Generator Service
Generates structured content strategy and post ideas using the Groq API.
Hardened with Pydantic schema validation, automatic retry, and clean error handling.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import groq
from groq import Groq
from pydantic import BaseModel, Field, ValidationError, field_validator

from config.settings import GROQ_MODEL, get_groq_api_key


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================

class ContentIdea(BaseModel):
    """Schema for an individual content idea."""
    title: str = Field(..., description="Catchy title for the content")
    content_type: str = Field(..., description="Format: Reel, Carousel, Post, Article, etc.")
    hook: str = Field(..., description="Attention-grabbing opening hook")
    caption: str = Field(..., description="Engaging caption or body copy")
    call_to_action: str = Field(..., description="Actionable closing call to action")
    hashtags: List[str] = Field(default_factory=list, description="Relevant hashtags")
    visual_concept: str = Field(..., description="Description of visual elements and aesthetics")
    image_prompt: str = Field(..., description="Detailed AI image generation prompt")
    target_audience: str = Field(default="", description="Target audience segment")
    duration_estimate: Optional[str] = Field(default=None, description="Estimated duration or read time")

    @field_validator("hashtags", mode="before")
    @classmethod
    def normalize_hashtags(cls, v: Any) -> List[str]:
        """Normalize hashtags into a clean list of strings with '#' prefix."""
        if isinstance(v, str):
            items = [item.strip() for item in v.replace(",", " ").split() if item.strip()]
            return [f"#{item.lstrip('#')}" for item in items]
        if isinstance(v, list):
            cleaned = []
            for item in v:
                if isinstance(item, str) and item.strip():
                    tag = item.strip()
                    cleaned.append(f"#{tag.lstrip('#')}" if not tag.startswith("#") else tag)
            return cleaned
        return []


class ContentStrategyResponse(BaseModel):
    """Schema for the complete content strategy response."""
    topic: str = Field(..., description="Topic of the strategy")
    target_audience: Optional[str] = Field(default=None, description="General target audience")
    campaign_objective: Optional[str] = Field(default=None, description="Campaign objective if provided")
    keywords: Optional[List[str]] = Field(default=None, description="Target keywords if provided")
    ideas: List[ContentIdea] = Field(..., min_length=1, description="List of generated content ideas")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _extract_json(text: str) -> str:
    """Extract and clean raw JSON string from LLM output."""
    cleaned = text.strip()

    # Remove markdown code fences if present
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):]
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    # Extract outermost JSON object if surrounded by chatter
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start:end + 1]

    return cleaned


def _apply_fallbacks(
    data: Dict[str, Any],
    fallback_audience: str,
    fallback_format: str,
    keywords: Optional[Union[str, List[str]]] = None,
    campaign_objective: Optional[str] = None
) -> Dict[str, Any]:
    """Ensure missing fields are populated with sensible defaults."""
    if not isinstance(data, dict):
        return data

    if not data.get("target_audience"):
        data["target_audience"] = fallback_audience

    if campaign_objective and not data.get("campaign_objective"):
        data["campaign_objective"] = campaign_objective

    if keywords and not data.get("keywords"):
        if isinstance(keywords, str):
            data["keywords"] = [k.strip() for k in keywords.split(",") if k.strip()]
        elif isinstance(keywords, list):
            data["keywords"] = keywords

    ideas = data.get("ideas")
    if isinstance(ideas, list):
        for idea in ideas:
            if isinstance(idea, dict):
                # Ensure target_audience is set
                if not idea.get("target_audience"):
                    idea["target_audience"] = fallback_audience

                # Ensure duration_estimate is set
                if not idea.get("duration_estimate"):
                    ctype = str(idea.get("content_type", fallback_format)).lower()
                    if any(term in ctype for term in ["reel", "short", "tiktok"]):
                        idea["duration_estimate"] = "30-60 seconds"
                    elif any(term in ctype for term in ["video", "youtube"]):
                        idea["duration_estimate"] = "3-5 minutes"
                    elif "carousel" in ctype:
                        idea["duration_estimate"] = "5-7 slides (~1 min read)"
                    elif any(term in ctype for term in ["article", "blog", "long-form"]):
                        idea["duration_estimate"] = "3-5 min read"
                    else:
                        idea["duration_estimate"] = "Quick read (~30s)"

    return data


# ============================================================
# MAIN GENERATOR FUNCTION
# ============================================================

def generate_content_ideas(
    topic: str,
    platform: str = "Instagram",
    audience: str = "General Audience",
    tone: str = "Creative",
    content_type: str = "Reels + Posts",
    number_of_ideas: int = 5,
    keywords: Optional[Union[str, List[str]]] = None,
    campaign_objective: Optional[str] = None,
    brand_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate social-media content ideas using Groq.

    Validates output against Pydantic schema, retries once on malformed output,
    and returns a clean dictionary. Injects active brand profile if configured.
    """
    # 1. Validate API Key
    api_key = get_groq_api_key()

    # If brand_profile not passed, try loading active profile from database
    if brand_profile is None:
        try:
            from database.db import get_active_brand_profile
            brand_profile = get_active_brand_profile()
        except Exception:
            brand_profile = None

    # 2. Format optional parameters for the prompt
    optional_instructions = []
    if keywords:
        kw_str = keywords if isinstance(keywords, str) else ", ".join(keywords)
        optional_instructions.append(f"Focus Keywords / SEO Tags: {kw_str}")
    if campaign_objective:
        optional_instructions.append(f"Campaign Objective: {campaign_objective}")

    if brand_profile:
        bp_lines = ["[ACTIVE BRAND IDENTITY & GUIDELINES]"]
        if brand_profile.get("name"):
            bp_lines.append(f"Brand Name: {brand_profile['name']}")
        if brand_profile.get("voice"):
            bp_lines.append(f"Brand Voice / Persona: {brand_profile['voice']}")
        if brand_profile.get("language"):
            bp_lines.append(f"Language: {brand_profile['language']}")
        if brand_profile.get("target_market"):
            bp_lines.append(f"Target Market: {brand_profile['target_market']}")
        if brand_profile.get("audience_age_group"):
            bp_lines.append(f"Target Age Group: {brand_profile['audience_age_group']}")
        if brand_profile.get("brand_colors"):
            bp_lines.append(f"Brand Visual Colors: {brand_profile['brand_colors']}")
        if brand_profile.get("business_objective"):
            bp_lines.append(f"Core Business Objective: {brand_profile['business_objective']}")
        if brand_profile.get("preferred_cta_style"):
            bp_lines.append(f"Preferred CTA Style: {brand_profile['preferred_cta_style']}")
        if brand_profile.get("words_to_avoid"):
            bp_lines.append(f"STRICTLY FORBIDDEN WORDS/PHRASES (DO NOT USE): {brand_profile['words_to_avoid']}")
        optional_instructions.append("\n".join(bp_lines))

    optional_block = "\n".join(optional_instructions)
    if optional_block:
        optional_block = f"\nAdditional Context:\n{optional_block}\n"

    # 3. Construct prompt
    prompt = f"""You are Fission AI, an intelligent AI-powered content strategy assistant.

The user wants to create content about:

Topic: {topic}
Platform: {platform}
Target audience: {audience}
Tone: {tone}
Content format: {content_type}
{optional_block}
Generate exactly {number_of_ideas} unique content ideas.

For every idea provide:
1. title: Catchy title for the content piece
2. content_type: The specific format (e.g. Reel, Carousel, Story, Single Post)
3. hook: An attention-grabbing first line or hook
4. caption: Full engaging caption/copy
5. call_to_action: Explicit CTA for the audience
6. hashtags: List of 3 to 6 relevant hashtags
7. visual_concept: Description of visual imagery, layout, and style
8. image_prompt: Detailed prompt suitable for AI image generation (diffusion models)
9. target_audience: Specific audience segment this idea targets
10. duration_estimate: Estimated time or length (e.g. "30-45 seconds" or "2 min read")

Return ONLY valid JSON.
Do not use Markdown formatting or code block wrappers.
Do not add explanations before or after.

Use exactly this structure:
{{
    "topic": "{topic}",
    "target_audience": "{audience}",
    "ideas": [
        {{
            "title": "Example title",
            "content_type": "Reel",
            "hook": "Example hook",
            "caption": "Example caption",
            "call_to_action": "Example CTA",
            "hashtags": ["#example", "#content", "#growth"],
            "visual_concept": "Description of the visual",
            "image_prompt": "Detailed AI image generation prompt with lighting and style",
            "target_audience": "{audience}",
            "duration_estimate": "30-60 seconds"
        }}
    ]
}}
"""

    client = Groq(api_key=api_key)

    # 4. Generate with retry once on malformed output
    max_attempts = 2
    last_validation_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are Fission AI, a professional social media content strategist. "
                        "You MUST respond ONLY with valid raw JSON conforming strictly to the requested schema. "
                        "Never include commentary, preambles, or markdown formatting."
                    )
                },
                {
                    "role": "user",
                    "content": prompt if attempt == 1 else (
                        f"{prompt}\n\n"
                        "IMPORTANT: Your previous output could not be parsed as valid JSON or was missing required fields. "
                        "You MUST output valid, parseable JSON conforming strictly to the structure."
                    )
                }
            ]

            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=4000
            )

        except groq.AuthenticationError:
            raise RuntimeError(
                "Groq authentication failed. Please check that your GROQ_API_KEY in .env is valid."
            )
        except groq.RateLimitError:
            raise RuntimeError(
                "Groq rate limit exceeded. Please wait a moment before trying again."
            )
        except groq.APIConnectionError:
            raise RuntimeError(
                "Could not connect to Groq API. Please check your internet connection."
            )
        except groq.GroqError as e:
            err_msg = getattr(e, "message", str(e))
            raise RuntimeError(f"Groq API error: {err_msg}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with Groq: {str(e)}")

        # Extract text
        if not response.choices or not response.choices[0].message.content:
            if attempt < max_attempts:
                continue
            raise RuntimeError("Groq returned an empty response.")

        raw_text = response.choices[0].message.content.strip()
        cleaned_text = _extract_json(raw_text)

        # Parse JSON
        try:
            parsed_data = json.loads(cleaned_text)
        except json.JSONDecodeError as jde:
            last_validation_error = f"JSON decode error: {jde}"
            if attempt < max_attempts:
                continue
            raise RuntimeError(
                f"Groq returned content, but it was not valid JSON after retry: {jde}"
            )

        # Apply default fallbacks for missing fields before validation
        parsed_data = _apply_fallbacks(
            parsed_data,
            fallback_audience=audience,
            fallback_format=content_type,
            keywords=keywords,
            campaign_objective=campaign_objective
        )

        # Validate with Pydantic schema
        try:
            strategy = ContentStrategyResponse.model_validate(parsed_data)
            return strategy.model_dump()
        except ValidationError as ve:
            last_validation_error = f"Schema validation error: {ve}"
            if attempt < max_attempts:
                continue
            raise RuntimeError(
                f"Groq response failed schema validation after retry: {ve}"
            )

    raise RuntimeError(
        f"Failed to generate valid content strategy after {max_attempts} attempts. Last error: {last_validation_error}"
    )
