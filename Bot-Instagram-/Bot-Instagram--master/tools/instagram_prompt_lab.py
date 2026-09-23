import argparse
import json
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

CASES_FILE = BASE_DIR / "tools" / "instagram_prompt_cases.json"


# ============================================================
# VALID OPTIONS
# ============================================================

VALID_MODES = {
    "normal_prospecting",
    "b2b_referral",
    "skip",
}

VALID_DIRECTNESS = {
    "direct",
    "indirect",
    "unclear",
    "none",
}

VALID_CONFIDENCE = {
    "high",
    "medium",
    "low",
}


REQUIRED_KEYS = {
    "skip_post",
    "mode",
    "selected_service",
    "b2b_target_type",
    "b2b_angle",
    "b2b_confidence",
    "request_directness",
    "service_match_reason",
    "comment",
}


# ============================================================
# CASES
# ============================================================

def load_cases():
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return data.get("cases", [])

    return data


def get_case(cases, case_name):
    for case in cases:
        if str(case.get("id")) == str(case_name):
            return case

    return None


# ============================================================
# PROMPT V4.1
# ============================================================

def build_prompt(case):
    campaign = case["campaign"]
    profile = case["profile"]
    post = case["post"]

    services = campaign["services"]

    return f"""
You are the commercial intelligence engine for an Instagram B2B prospecting system.

Your job is NOT simply to comment on Instagram posts.

Your job is to understand:

1. What type of business the profile belongs to.
2. Whether the profile is relevant to the campaign.
3. Whether the opportunity is a direct prospect or a B2B referral/partner opportunity.
4. Which campaign service is the MOST commercially relevant.
5. Whether the post should be skipped.

IMPORTANT:
Analyze the BUSINESS, not only the individual post.

A business can be a valid prospect even when the current post does not explicitly ask for the service.

============================================================
CAMPAIGN
============================================================

Campaign name:
{campaign["name"]}

Available services:
{services}

============================================================
PROFILE
============================================================

Username:
{profile["username"]}

Industry:
{profile["industry"]}

Bio:
{profile.get("bio", "")}

============================================================
POST
============================================================

Caption:
{post["caption"]}

============================================================
CORE COMMERCIAL UNDERSTANDING
============================================================

First identify the real-world business represented by the profile.

Use ALL available signals:

- username
- industry
- bio
- caption
- services mentioned
- type of customers served
- type of projects shown
- relationship between the business and the campaign services

Do NOT classify a business only from keywords in the caption.

The business context has priority over isolated words.

============================================================
DIRECT PROSPECT VS B2B REFERRAL
============================================================

Use "normal_prospecting" when the business itself is a potential customer
of the campaign.

Use "b2b_referral" when the business is a complementary professional,
contractor, vendor, property manager, landscaper, photographer, etc.,
that could refer customers, subcontract work, or collaborate with the
campaign business.

Examples:

Property Manager + Commercial Cleaning
=> b2b_referral
=> Commercial Cleaning

General Contractor + Fence Installation
=> b2b_referral
=> Fence Installation

Landscaper + Fence Installation
=> b2b_referral
=> Fence Installation

Wedding Photographer + Digital Marketing
=> b2b_referral
=> Social Media Management

IMPORTANT:
A business does NOT need to explicitly request a service in the post to
be a valid prospect.

============================================================
SERVICE SELECTION — VERY IMPORTANT
============================================================

When skip_post is false, selected_service MUST be exactly one of:

{services}

Never return multiple services.

selected_service must be a SINGLE STRING.

Do not return an array.

Do not select a service merely because it is mentioned in the caption.

Select the service that represents the strongest commercial opportunity
for THIS BUSINESS.

============================================================
REAL ESTATE
============================================================

For real estate agents, realtors, brokers and similar property sales
professionals:

If the opportunity is primarily about attracting buyers, sellers,
property inquiries, appointments or prospects:

=> select "Lead Generation"

Do NOT automatically select "Social Media Management" merely because
the realtor posts listings on Instagram.

A real estate listing is evidence that the agent is actively marketing
properties, but the commercial objective is normally generating buyer
and seller leads.

Therefore:

Realtor + property listing
=> Lead Generation

Realtor + wants more buyers/sellers/inquiries
=> Lead Generation

Realtor + explicitly needs content/social presence management
=> Social Media Management

Realtor + explicitly needs paid campaigns/ads
=> Digital Advertising

When the context is ambiguous but the profile is clearly a realtor and
the available services include Lead Generation, prefer Lead Generation
over Social Media Management.

============================================================
LOCAL SERVICE BUSINESSES
============================================================

For restaurants, beauty studios, auto shops, photographers,
contractors and other local businesses:

Consider the actual business need.

If the business mainly needs a stronger organic presence, content,
posting consistency or Instagram management:

=> Social Media Management

If the strongest opportunity is acquiring customers, inquiries,
appointments or leads:

=> Lead Generation

If the strongest opportunity is paid advertising:

=> Digital Advertising

Do not force Lead Generation when there is no reasonable evidence of
a lead-generation opportunity.

Do not force Digital Advertising without evidence of a paid-ad
opportunity.

============================================================
B2B REFERRAL BUSINESSES
============================================================

When a complementary business can naturally refer or subcontract the
campaign service, use:

=> mode = "b2b_referral"

IMPORTANT:

Being a referral partner does NOT automatically mean selecting
Lead Generation.

The selected service must reflect the most natural service relationship
between the campaign and the partner business.

============================================================
PHOTOGRAPHERS
============================================================

For photographers, wedding photographers, event photographers and
similar visual-content businesses:

When the campaign is a Digital Marketing Agency with services such as:

- Social Media Management
- Lead Generation
- Digital Advertising

and the photographer is a complementary business that could collaborate
with or refer clients to the agency:

=> mode = "b2b_referral"

=> selected_service = "Social Media Management"

unless there is explicit evidence that the photographer is specifically
looking for lead generation.

Do NOT select Lead Generation merely because photographers work with
potential customers or couples.

The fact that a photographer can refer potential clients does not by
itself make Lead Generation the correct selected_service.

For example:

Wedding Photographer + Digital Marketing Agency
=> b2b_referral
=> Social Media Management

Wedding Photographer + explicit request for more inquiries/leads
=> b2b_referral or normal_prospecting depending on context
=> Lead Generation

Wedding Photographer + explicit need for paid advertising
=> Digital Advertising

Wedding Photographer + general collaboration/referral opportunity
=> Social Media Management

The default commercial interpretation for a photographer partnership is
Social Media Management because photographers are complementary visual
content professionals and the agency can provide ongoing social-media
strategy, content management and online presence support.

============================================================
LANDSCAPERS / CONTRACTORS / PROPERTY MANAGERS
============================================================

Landscaping business + Fence Installation
=> b2b_referral
=> Fence Installation

General contractor + Fence Installation
=> b2b_referral
=> Fence Installation

Property manager + Commercial Cleaning
=> b2b_referral
=> Commercial Cleaning

These partner-specific campaign services take priority over generic
digital-marketing service selection.

============================================================
GENERAL B2B RULE
============================================================

Use b2b_referral when the business is a complementary professional that
can naturally refer, subcontract or collaborate.

However:

b2b_referral determines the MODE.

It does NOT by itself determine the selected_service.

selected_service must still be chosen according to the specific
relationship between the partner and the campaign.

============================================================
B2B CONFIDENCE — MANDATORY FIELD
============================================================

b2b_confidence is REQUIRED in every response.

It MUST NEVER be empty.

Use:

"high"
=> when the business relationship is clearly identifiable.

"medium"
=> when there is a reasonable commercial relationship but some
uncertainty remains.

"low"
=> when the profile is relevant but there is little or no evidence of
a B2B referral relationship.

IMPORTANT:

For normal_prospecting businesses such as restaurants, beauty studios,
auto shops and realtors:

If there is no B2B referral relationship:

=> b2b_confidence = "low"

Do NOT return:

""
null
[]
or any other empty value.

Examples:

Restaurant + Digital Marketing
=> mode = normal_prospecting
=> b2b_confidence = low

Beauty Studio + Digital Marketing
=> mode = normal_prospecting
=> b2b_confidence = low

Auto Repair Shop + Digital Marketing
=> mode = normal_prospecting
=> b2b_confidence = low

Realtor + Digital Marketing
=> mode = normal_prospecting
=> b2b_confidence = low

Property Manager + Commercial Cleaning
=> mode = b2b_referral
=> b2b_confidence = high

General Contractor + Fence Installation
=> mode = b2b_referral
=> b2b_confidence = high

Landscaper + Fence Installation
=> mode = b2b_referral
=> b2b_confidence = high

Wedding Photographer + Digital Marketing
=> mode = b2b_referral
=> b2b_confidence = high

For skip cases:

=> b2b_confidence = "low"

============================================================
REQUEST DIRECTNESS — MANDATORY FIELD
============================================================

request_directness describes whether the POST itself contains a request
for the service.

Use:

"direct"
=> The post explicitly asks for the service, provider, recommendation,
help, quote, leads, advertising, social media management, etc.

"indirect"
=> The post does not explicitly ask for the service, but there is a
reasonable commercial opportunity based on the business context.

"unclear"
=> There is some indication of a possible request, but the intent
cannot be determined reliably.

"none"
=> Only use this for skip_post = true.

IMPORTANT:

A valid prospect does NOT require a direct request.

For example:

Restaurant posting its menu
=> normal_prospecting
=> request_directness = "indirect"

Beauty studio showing client work
=> normal_prospecting
=> request_directness = "indirect"

Realtor posting a property
=> normal_prospecting
=> request_directness = "indirect"

Auto shop posting completed brake work
=> normal_prospecting
=> request_directness = "indirect"

Property manager showing a prepared commercial property
=> b2b_referral
=> request_directness = "indirect"

Do NOT use "none" for a valid prospect.

============================================================
SKIP RULES
============================================================

Set:

skip_post = true
mode = "skip"
request_directness = "none"

when:

1. The profile is clearly personal/non-business and unrelated.
2. The profile is a direct competitor of the campaign.
3. There is no meaningful commercial relationship with the campaign.
4. The content is clearly irrelevant to the campaign and business.

Direct competitors must NEVER be treated as referral partners.

When skip_post = true:

selected_service MUST be ""

comment MUST be ""

b2b_target_type MUST be ""

b2b_angle MUST be ""

b2b_confidence MUST be "low"

service_match_reason may explain why the profile is skipped.

============================================================
COMPETITOR DETECTION
============================================================

Compare the profile's industry, bio and business activity against the
campaign.

If the profile provides the same core service as the campaign:

=> skip_post = true
=> mode = "skip"

Example:

Campaign:
Commercial Cleaning

Profile:
Commercial cleaning and janitorial services

=> direct competitor
=> SKIP

============================================================
COMMENT RULES
============================================================

The comment must:

- sound natural
- be relevant to the actual post
- acknowledge the content first
- avoid sounding like spam
- avoid aggressive sales language
- avoid pretending to know facts not provided
- make the commercial connection naturally
- use Spanish when appropriate to the campaign/personality context

For referral opportunities, the comment can softly mention collaboration,
referrals, subcontracting or complementary services.

For direct prospects, the comment should softly introduce the relevant
campaign service without making the comment sound like an advertisement.

IMPORTANT:

Do not invent facts about the business.

Do not claim that the business "needs" a service as a certainty when the
post does not establish that.

Prefer language such as:

"si alguna vez..."
"si en algún momento..."
"puede ser interesante..."
"si necesitáis apoyo..."

instead of:

"sé que necesitas..."
"tu negocio necesita..."
"te hace falta..."

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

The JSON object MUST contain exactly these fields:

{{
  "skip_post": true_or_false,
  "mode": "skip" | "normal_prospecting" | "b2b_referral",
  "selected_service": "",
  "b2b_target_type": "",
  "b2b_angle": "",
  "b2b_confidence": "high" | "medium" | "low",
  "request_directness": "none" | "indirect" | "direct" | "unclear",
  "service_match_reason": "",
  "comment": ""
}}

============================================================
ABSOLUTE OUTPUT REQUIREMENTS
============================================================

Before returning the JSON, verify all of these:

1. The response contains EXACTLY 9 fields.

2. skip_post is a real JSON boolean:
   true or false

3. mode is exactly one of:
   skip
   normal_prospecting
   b2b_referral

4. selected_service is a SINGLE STRING.

5. If skip_post=false:
   selected_service MUST be exactly one of:
   {services}

6. If skip_post=true:
   selected_service MUST be ""

7. b2b_confidence MUST ALWAYS be one of:
   high
   medium
   low

8. b2b_confidence MUST NEVER be empty.

9. If mode=normal_prospecting and there is no B2B referral relationship:
   b2b_confidence = "low"

10. If skip_post=true:
    request_directness = "none"

11. If skip_post=false and there is no explicit request:
    request_directness = "indirect"

12. If skip_post=true:
    comment = ""

13. If skip_post=false:
    comment MUST NOT be empty.

14. Do NOT return Markdown.

15. Do NOT return ```json.

16. Do NOT return explanations outside the JSON.

17. Do NOT return arrays for any field.

============================================================
FINAL DECISION CHECK
============================================================

Internally verify:

1. Is this actually a business?
2. Is it relevant to the campaign?
3. Is it a competitor?
4. Is it a direct prospect or referral partner?
5. What is the BUSINESS'S strongest commercial opportunity?
6. Is selected_service one of the available campaign services?
7. For real estate, did I consider Lead Generation before Social Media
   Management?
8. If skip_post=true, is mode="skip"?
9. If skip_post=true, is request_directness="none"?
10. If skip_post=true, are selected_service and comment empty?
11. Is b2b_confidence populated with high, medium or low?
12. If normal_prospecting without B2B relationship, is confidence="low"?
13. Is request_directness "indirect" when the opportunity exists but the
    post does not explicitly ask for the service?
14. Is the comment natural and relevant?

Return ONLY JSON.
"""


# ============================================================
# OFFLINE RESULT
# ============================================================

def offline_result(case):
    expected = case.get("expected") or {}

    mode = str(
        expected.get("mode", "normal_prospecting")
    ).strip().lower()

    # Test cases may omit skip_post because mode="skip" is already
    # unambiguous. Infer it here so the offline harness validates the
    # same contract as the live prompt.
    skip_post = bool(
        expected.get("skip_post", mode == "skip")
    )

    if skip_post:
        return {
            "skip_post": True,
            "mode": "skip",
            "selected_service": "",
            "b2b_target_type": "",
            "b2b_angle": "",
            "b2b_confidence": "low",
            "request_directness": "none",
            "service_match_reason": "",
            "comment": "",
        }

    return {
        "skip_post": False,
        "mode": mode,
        "selected_service": expected.get(
            "selected_service",
            "",
        ),
        "b2b_target_type": expected.get(
            "b2b_target_type",
            "",
        ),
        "b2b_angle": expected.get(
            "b2b_angle",
            "",
        ),
        "b2b_confidence": expected.get(
            "b2b_confidence",
            "high" if mode == "b2b_referral" else "low",
        ),
        "request_directness": expected.get(
            "request_directness",
            "indirect",
        ),
        "service_match_reason": expected.get(
            "service_match_reason",
            "Offline test result.",
        ),
        "comment": expected.get(
            "comment",
            "Test comment for the Instagram prompt laboratory.",
        ),
    }


# ============================================================
# AI CLIENT
# ============================================================

def create_ai_service(personality_id):
    """
    Importa AIAPI de forma robusta cuando el script se ejecuta como:

        python tools\\instagram_prompt_lab.py

    Esto evita problemas de import path como:

        No module named 'app'
    """

    root = str(BASE_DIR)

    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        from app.api.ai_api import AIAPI

    except Exception as exc:

        raise RuntimeError(
            "No se pudo importar "
            f"app.api.ai_api.AIAPI: {exc}"
        ) from exc

    print("[AIAPI] Preparando cliente...")

    client = AIAPI()

    print("[AIAPI] Cliente preparado.")

    return client, personality_id


# ============================================================
# AI EXECUTION
# ============================================================

def call_ai(
    client,
    prompt,
    personality_id,
):
    """
    Usa el AIAPI real del proyecto.

    El proyecto actual expone:
        get_bot_ia_long_prompt()
    """

    if not hasattr(
        client,
        "get_bot_ia_long_prompt",
    ):

        raise RuntimeError(
            "AIAPI no contiene "
            "get_bot_ia_long_prompt()."
        )

    success, data = client.get_bot_ia_long_prompt(
        bot_personality_id=personality_id,
        user_prompt=prompt,
    )

    if not success:

        raise RuntimeError(
            f"AIAPI devolvió error: {data!r}"
        )

    return normalize_ai_result(data)


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_ai_result(result):
    """
    Convierte la respuesta de AIAPI en un dict limpio.

    También maneja respuestas envueltas en:

        {
            "result": {...}
        }

    y elimina Markdown fences si aparecen.
    """

    if isinstance(result, dict):

        if (
            "result" in result
            and isinstance(
                result["result"],
                dict,
            )
        ):
            result = result["result"]

        return normalize_result_fields(result)

    if not isinstance(result, str):

        raise ValueError(
            "La IA devolvió un tipo de respuesta "
            "no compatible."
        )

    text = result.strip()

    # --------------------------------------------------------
    # Remove Markdown fences
    # --------------------------------------------------------

    if text.startswith("```"):

        lines = text.splitlines()

        if (
            lines
            and lines[0]
            .strip()
            .startswith("```")
        ):
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        text = "\n".join(lines).strip()

        if text.lower().startswith("json"):
            text = text[4:].strip()

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:

        parsed = json.loads(text)

    except json.JSONDecodeError as exc:

        raise ValueError(
            "La IA no devolvió JSON válido.\n"
            f"Respuesta:\n{text}"
        ) from exc

    if not isinstance(parsed, dict):

        raise ValueError(
            "La IA debe devolver un objeto JSON."
        )

    return normalize_result_fields(parsed)


def normalize_result_fields(result):
    """
    Normaliza todos los campos importantes antes de validar.
    """

    result = dict(result)

    # --------------------------------------------------------
    # selected_service
    # --------------------------------------------------------

    value = result.get(
        "selected_service",
        "",
    )

    if isinstance(value, list):

        cleaned = []

        for item in value:

            if item is None:
                continue

            item = str(item).strip()

            if item:
                cleaned.append(item)

        # El laboratorio exige EXACTAMENTE un servicio.
        result["selected_service"] = (
            cleaned[0]
            if cleaned
            else ""
        )

    elif value is None:

        result["selected_service"] = ""

    else:

        result["selected_service"] = (
            str(value).strip()
        )

    # --------------------------------------------------------
    # String fields
    # --------------------------------------------------------

    string_fields = [
        "mode",
        "b2b_target_type",
        "b2b_angle",
        "b2b_confidence",
        "request_directness",
        "service_match_reason",
        "comment",
    ]

    for field in string_fields:

        value = result.get(
            field,
            "",
        )

        if value is None:

            result[field] = ""

        elif isinstance(value, list):

            result[field] = " ".join(
                str(item).strip()
                for item in value
                if str(item).strip()
            ).strip()

        else:

            result[field] = (
                str(value).strip()
            )

    # --------------------------------------------------------
    # skip_post
    # --------------------------------------------------------

    value = result.get(
        "skip_post",
        False,
    )

    if isinstance(value, str):

        normalized = (
            value.strip().lower()
        )

        if normalized in {
            "true",
            "1",
            "yes",
            "si",
            "sí",
        }:

            result["skip_post"] = True

        elif normalized in {
            "false",
            "0",
            "no",
        }:

            result["skip_post"] = False

    # --------------------------------------------------------
    # Defensive defaults
    # --------------------------------------------------------
    #
    # IMPORTANTE:
    # Estos defaults NO reemplazan la validación.
    # Solamente evitan que un campo obligatorio quede vacío
    # cuando la IA omite un campo que puede inferirse de forma
    # segura.
    #
    # Para b2b_confidence:
    # - skip => low
    # - normal prospect => low
    # - referral => low si la IA omitió el campo
    #
    # La validación sigue comprobando que sea válido.
    # --------------------------------------------------------

    confidence = result.get(
        "b2b_confidence",
        "",
    )

    if not confidence:

        result["b2b_confidence"] = "low"

    # --------------------------------------------------------
    # Defensive request_directness
    # --------------------------------------------------------

    directness = result.get(
        "request_directness",
        "",
    )

    if not directness:

        if result.get(
            "skip_post",
            False,
        ):

            result["request_directness"] = (
                "none"
            )

        else:

            result["request_directness"] = (
                "indirect"
            )

    # --------------------------------------------------------
    # Skip consistency normalization
    # --------------------------------------------------------

    if result.get(
        "skip_post",
        False,
    ):

        result["mode"] = "skip"
        result["selected_service"] = ""
        result["b2b_target_type"] = ""
        result["b2b_angle"] = ""
        result["b2b_confidence"] = "low"
        result["request_directness"] = "none"
        result["comment"] = ""

    return result


# ============================================================
# VALIDATION
# ============================================================

def safe_lower(value):
    """
    Evita:

        'list' object has no attribute 'lower'

    La normalización debería evitar listas, pero esta función
    mantiene la validación resistente.
    """

    if value is None:
        return ""

    if isinstance(value, list):

        value = (
            value[0]
            if value
            else ""
        )

    return str(value).strip().lower()


def validate_result(
    case,
    result,
):
    errors = []

    # --------------------------------------------------------
    # Basic object
    # --------------------------------------------------------

    if not isinstance(
        result,
        dict,
    ):

        return [
            "La IA debe devolver un objeto JSON."
        ]

    missing = (
        REQUIRED_KEYS
        - set(result.keys())
    )

    if missing:

        errors.append(
            "Faltan campos: "
            + ", ".join(
                sorted(missing)
            )
        )

        return errors

    # --------------------------------------------------------
    # Types
    # --------------------------------------------------------

    if not isinstance(
        result["skip_post"],
        bool,
    ):

        errors.append(
            "skip_post debe ser booleano."
        )

    # --------------------------------------------------------
    # Mode
    # --------------------------------------------------------

    mode = safe_lower(
        result["mode"]
    )

    if mode not in VALID_MODES:

        errors.append(
            f"mode inválido: "
            f"{result['mode']!r}"
        )

    # --------------------------------------------------------
    # Directness
    # --------------------------------------------------------

    directness = safe_lower(
        result["request_directness"]
    )

    if directness not in VALID_DIRECTNESS:

        errors.append(
            "request_directness inválido: "
            f"{result['request_directness']!r}"
        )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    confidence = safe_lower(
        result["b2b_confidence"]
    )

    if confidence not in VALID_CONFIDENCE:

        errors.append(
            "b2b_confidence inválido: "
            f"{result['b2b_confidence']!r}"
        )

    # --------------------------------------------------------
    # Skip consistency
    # --------------------------------------------------------

    if result["skip_post"]:

        if mode != "skip":

            errors.append(
                "skip_post=True exige "
                "mode='skip'."
            )

        if directness != "none":

            errors.append(
                "skip_post=True exige "
                "request_directness='none'."
            )

        if result.get(
            "selected_service",
            "",
        ):

            errors.append(
                "skip_post=True exige "
                "selected_service vacío."
            )

        if result.get(
            "comment",
            "",
        ):

            errors.append(
                "skip_post=True exige "
                "comment vacío."
            )

        if result.get(
            "b2b_target_type",
            "",
        ):

            errors.append(
                "skip_post=True exige "
                "b2b_target_type vacío."
            )

        if result.get(
            "b2b_angle",
            "",
        ):

            errors.append(
                "skip_post=True exige "
                "b2b_angle vacío."
            )

        if confidence != "low":

            errors.append(
                "skip_post=True exige "
                "b2b_confidence='low'."
            )

    else:

        if mode == "skip":

            errors.append(
                "skip_post=False no puede "
                "tener mode='skip'."
            )

        services = (
            case.get("campaign", {})
            .get("services")
            or case.get("campaign", {})
            .get("services_snapshot")
            or []
        )

        allowed_services = {
            str(service)
            .strip()
            .lower()
            for service in services
            if str(service).strip()
        }

        selected_service = safe_lower(
            result["selected_service"]
        )

        if (
            selected_service
            not in allowed_services
        ):

            errors.append(
                "selected_service debe ser "
                "uno de: "
                f"{services}; obtenido="
                f"{result['selected_service']!r}"
            )

        if not result.get(
            "comment",
            "",
        ).strip():

            errors.append(
                "Un resultado no omitido debe "
                "contener comment."
            )

        # Un prospecto válido nunca puede tener
        # request_directness = none.
        if directness == "none":

            errors.append(
                "skip_post=False exige que "
                "request_directness no sea 'none'."
            )

    # --------------------------------------------------------
    # Expected behavior
    # --------------------------------------------------------

    expected = (
        case.get("expected")
        or {}
    )

    if expected:

        expected_mode = safe_lower(
            expected.get("mode")
        )

        if (
            expected_mode
            and mode != expected_mode
        ):

            errors.append(
                f"mode esperado={expected_mode!r}, "
                f"obtenido={mode!r}"
            )

        expected_service = safe_lower(
            expected.get(
                "selected_service"
            )
        )

        if expected_service:

            obtained_service = safe_lower(
                result["selected_service"]
            )

            if (
                obtained_service
                != expected_service
            ):

                errors.append(
                    "selected_service esperado="
                    f"{expected_service!r}, "
                    "obtenido="
                    f"{obtained_service!r}"
                )

        # ----------------------------------------------------
        # selected_service_options
        # ----------------------------------------------------

        allowed_options = (
            expected.get(
                "selected_service_options"
            )
            or []
        )

        if allowed_options:

            normalized_options = {
                safe_lower(item)
                for item in allowed_options
                if safe_lower(item)
            }

            obtained_service = safe_lower(
                result["selected_service"]
            )

            if (
                obtained_service
                not in normalized_options
            ):

                errors.append(
                    "selected_service "
                    f"{obtained_service!r} "
                    "no está entre las opciones "
                    f"válidas="
                    f"{sorted(normalized_options)}"
                )

        # ----------------------------------------------------
        # skip
        # ----------------------------------------------------

        if "skip_post" in expected:

            expected_skip = bool(
                expected["skip_post"]
            )

            if (
                result["skip_post"]
                != expected_skip
            ):

                errors.append(
                    "skip_post esperado="
                    f"{expected_skip!r}, "
                    "obtenido="
                    f"{result['skip_post']!r}"
                )

        # ----------------------------------------------------
        # directness
        # ----------------------------------------------------

        expected_directness = safe_lower(
            expected.get(
                "request_directness"
            )
        )

        if (
            expected_directness
            and directness
            != expected_directness
        ):

            errors.append(
                "request_directness esperado="
                f"{expected_directness!r}, "
                "obtenido="
                f"{directness!r}"
            )

    # ========================================================
    # KNOWN REFERRAL CASES
    # ========================================================

    referral_cases = {
        "cleaning_property_manager",
        "fencing_contractor",
        "landscaping",
        "photographer",
    }

    case_id = str(
        case.get(
            "id",
            "",
        )
    )

    if (
        case_id in referral_cases
        and not result["skip_post"]
    ):

        if mode != "b2b_referral":

            errors.append(
                "Oportunidad B2B/referral "
                "detectada pero mode no es "
                "'b2b_referral'."
            )

        if confidence not in {
            "high",
            "medium",
        }:

            errors.append(
                "Un caso B2B/referral conocido "
                "debe tener b2b_confidence "
                "high o medium."
            )

    # ========================================================
    # SKIP CASES
    # ========================================================

    skip_cases = {
        "irrelevant_personal",
        "competitor",
    }

    if case_id in skip_cases:

        if not result["skip_post"]:

            errors.append(
                f"El caso {case_id!r} "
                "debe ser skip_post=true."
            )

    return errors


# ============================================================
# OUTPUT
# ============================================================

def print_result(
    result,
    validation_errors=None,
):
    print("AI RESULT")
    print("-" * 70)

    for key in [
        "skip_post",
        "mode",
        "selected_service",
        "b2b_target_type",
        "b2b_angle",
        "b2b_confidence",
        "request_directness",
        "service_match_reason",
        "comment",
    ]:

        print(
            f"{key}: "
            f"{result.get(key, '')}"
        )

    print()

    print("VALIDATION")
    print("-" * 70)

    if validation_errors:

        for error in validation_errors:
            print(f"✗ {error}")

        print()
        print("RESULT: FAIL")

    else:

        print("✓ JSON válido")

        print(
            "✓ Resultado compatible "
            "con las reglas del laboratorio"
        )

        print()
        print("RESULT: PASS")


def print_case(
    case,
    index,
    total,
):
    print("=" * 70)

    print(
        f"[{index}/{total}] "
        f"{case.get('id', '')} — "
        f"{case.get('title', '')}"
    )

    print("=" * 70)
    print()

    campaign = (
        case.get("campaign")
        or {}
    )

    profile = (
        case.get("profile")
        or {}
    )

    post = (
        case.get("post")
        or {}
    )

    services = (
        campaign.get("services")
        or campaign.get(
            "services_snapshot"
        )
        or []
    )

    print("CAMPAIGN")

    print(
        f"  Name: "
        f"{campaign.get('name', '')}"
    )

    print(
        "  Services: "
        + ", ".join(
            map(
                str,
                services,
            )
        )
    )

    print()

    print("PROFILE")

    print(
        f"  Username: "
        f"{profile.get('username', '')}"
    )

    print(
        f"  Industry: "
        f"{profile.get('industry', '')}"
    )

    if profile.get("bio"):

        print(
            f"  Bio: "
            f"{profile.get('bio')}"
        )

    print()

    print("POST")

    print(
        f"  Caption: "
        f"{post.get('caption', '')}"
    )

    print()


# ============================================================
# MAIN
# ============================================================

def run():
    parser = argparse.ArgumentParser(
        description="Instagram Prompt Lab V4.1"
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Ejecutar contra la IA real.",
    )

    parser.add_argument(
        "--case",
        help="Ejecutar solamente un caso.",
    )

    parser.add_argument(
        "--personality-id",
        type=int,
        default=7,
        help="Personality ID.",
    )

    parser.add_argument(
        "--save-prompts",
        action="store_true",
        help=(
            "Guardar prompts generados en "
            "tools/generated_prompts/"
        ),
    )

    args = parser.parse_args()

    print("=" * 70)
    print("INSTAGRAM PROMPT LAB V4.1")
    print("=" * 70)
    print()

    print(
        f"Modo: "
        f"{'LIVE AI' if args.live else 'OFFLINE'}"
    )

    print("Instagram: NO")
    print("Selenium: NO")
    print("Follow: NO")
    print("Like: NO")
    print("Comment real: NO")
    print()

    # --------------------------------------------------------
    # Load cases
    # --------------------------------------------------------

    try:

        cases = load_cases()

    except Exception as exc:

        print(
            f"ERROR cargando casos: {exc}"
        )

        return 1

    # --------------------------------------------------------
    # Filter case
    # --------------------------------------------------------

    if args.case:

        cases = [
            case
            for case in cases
            if str(
                case.get("id")
            )
            == str(args.case)
        ]

        if not cases:

            print(
                f"No existe el caso: "
                f"{args.case}"
            )

            return 1

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    ai_client = None

    if args.live:

        if not args.personality_id:

            print(
                "ERROR: --live requiere "
                "--personality-id."
            )

            return 1

        try:

            (
                ai_client,
                personality_id,
            ) = create_ai_service(
                args.personality_id
            )

        except Exception as exc:

            print(
                "ERROR inicializando AI API:"
            )

            print(exc)

            return 1

    else:

        personality_id = (
            args.personality_id
        )

    # --------------------------------------------------------
    # Prompt directory
    # --------------------------------------------------------

    prompt_dir = (
        BASE_DIR
        / "tools"
        / "generated_prompts"
    )

    if args.save_prompts:

        prompt_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # --------------------------------------------------------
    # Counters
    # --------------------------------------------------------

    total = len(cases)

    passed = 0
    failed = 0
    errors = 0

    # ========================================================
    # CASE LOOP
    # ========================================================

    for index, case in enumerate(
        cases,
        start=1,
    ):

        print_case(
            case,
            index,
            total,
        )

        try:

            prompt = build_prompt(case)

            # ------------------------------------------------
            # Save prompt
            # ------------------------------------------------

            if args.save_prompts:

                prompt_file = (
                    prompt_dir
                    / f"{case.get('id', index)}.txt"
                )

                with open(
                    prompt_file,
                    "w",
                    encoding="utf-8",
                ) as file:

                    file.write(prompt)

                print(
                    f"[PROMPT] Guardado: "
                    f"{prompt_file}"
                )

            # ------------------------------------------------
            # Execute
            # ------------------------------------------------

            if args.live:

                result = call_ai(
                    client=ai_client,
                    prompt=prompt,
                    personality_id=personality_id,
                )

            else:

                result = offline_result(
                    case
                )

            # ------------------------------------------------
            # Normalize
            # ------------------------------------------------

            result = normalize_result_fields(
                result
            )

            # ------------------------------------------------
            # Validate
            # ------------------------------------------------

            validation_errors = (
                validate_result(
                    case,
                    result,
                )
            )

            # ------------------------------------------------
            # Print
            # ------------------------------------------------

            print_result(
                result,
                validation_errors,
            )

            # ------------------------------------------------
            # Counters
            # ------------------------------------------------

            if validation_errors:

                failed += 1

            else:

                passed += 1

        except Exception as exc:

            errors += 1

            print()
            print(
                "ERROR ejecutando caso:"
            )

            print(
                repr(exc)
            )

        print()

    # ========================================================
    # SUMMARY
    # ========================================================

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(
        f"TOTAL : {total}"
    )

    print(
        f"PASS  : {passed}"
    )

    print(
        f"FAIL  : {failed}"
    )

    print(
        f"ERROR : {errors}"
    )

    print()

    if args.live:

        print(
            "La IA fue ejecutada."
        )

        print(
            "Instagram NO fue ejecutado."
        )

    else:

        print(
            "Modo offline: "
            "NO se llamó a la IA."
        )

        print(
            "Instagram NO fue ejecutado."
        )

    print()

    if (
        failed == 0
        and errors == 0
    ):

        print(
            "✓ INSTAGRAM PROMPT LAB V4.1 "
            "COMPLETADO"
        )

        return 0

    print(
        "✗ INSTAGRAM PROMPT LAB V4.1 "
        "DETECTÓ PROBLEMAS"
    )

    return 1


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    raise SystemExit(
        run()
    )
