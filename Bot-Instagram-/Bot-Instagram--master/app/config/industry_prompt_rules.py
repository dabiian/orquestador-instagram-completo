"""Industry rules carried from the Facebook campaign prompts.

Instagram keeps its own architecture.  These files are used only as the
long-form business-rule layer so the generated behaviour preserves the
campaign rules without copying Facebook's runtime implementation.
"""
from __future__ import annotations

from pathlib import Path
import unicodedata

_BASE = Path(__file__).resolve().parent / "prompts" / "facebook_compatible"

# The source campaign document currently contains the full long-form comment
# prompts for these campaign types.  Other campaign types use the structured
# rules below plus their campaign services/strategy, rather than inventing a
# Facebook prompt that was not supplied in the source material.
_PROMPT_FILES = {
    "marketing": "marketing_comment_prompt.txt",
    "fences": "fences_comment_prompt.txt",
    "spa": "spa_comment_prompt.txt",
    "spa colombia": "spa_comment_prompt.txt",
    "botanica": "botanica_comment_prompt.txt",
    "botanicas": "botanica_comment_prompt.txt",
    "abogados": "abogados_comment_prompt.txt",
}

_STRUCTURED_RULES = {
    "cleaning": """
INDUSTRY RULES — CLEANING
- Offer only services supported by CAMPAIGN_SERVICES.
- Valid commercial contexts include offices, buildings, facilities, industrial/commercial properties,
  janitorial needs, disinfection and facility maintenance when supported by the campaign.
- Do not treat property management, real estate, contractors, landscapers, movers or handyman profiles
  as direct cleaning competitors unless they actually offer cleaning services.
- Do not invent property size, cleaning frequency, price, staffing, availability or results.
- Skip personal, unrelated, entertainment-only and unsupported posts.
- Choose exactly one supported service when commenting.
- Keep B2B referral language separate from normal customer prospecting.
""",
    "construction": """
INDUSTRY RULES — CONSTRUCTION
- Offer only services supported by CAMPAIGN_SERVICES.
- Match construction, remodeling, renovation, building and general contracting needs only when supported.
- Do not invent project scope, budget, timeline, permits, location or materials.
- Do not block adjacent professionals merely because they are architects, realtors, cleaners,
  landscapers, plumbers, roofers or HVAC providers unless they offer the campaign's direct services.
- Choose exactly one supported service and skip weak or forced opportunities.
""",
    "real_estate": """
INDUSTRY RULES — REAL ESTATE
- Offer only services supported by CAMPAIGN_SERVICES.
- Distinguish real-estate businesses from buyers, sellers, renters and unrelated personal profiles.
- Do not invent property value, location, financing, availability, price or transaction details.
- Mortgage, inspection, title, insurance, construction, cleaning and moving are adjacent/referral niches,
  not direct competitors unless they also offer the campaign's core real-estate services.
- Choose exactly one supported service and skip unsupported opportunities.
""",
}


def normalize_campaign_type(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = " ".join(text.split())
    aliases = {
        "botanica espiritual": "botanica",
        "botanicas": "botanica",
        "spa colombia": "spa colombia",
        "spa/medicina estetica": "spa",
        "legal": "abogados",
        "lawyers": "abogados",
        "law firm": "abogados",
        "fencing": "fences",
        "cleaner": "cleaning",
    }
    return aliases.get(text, text)


def get_industry_prompt_rules(campaign_type: object) -> str:
    key = normalize_campaign_type(campaign_type)
    filename = _PROMPT_FILES.get(key)
    if filename:
        path = _BASE / filename
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            pass
    return _STRUCTURED_RULES.get(key, "")
