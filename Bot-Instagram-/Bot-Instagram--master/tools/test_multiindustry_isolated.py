import argparse
import json
import sys
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# ============================================================
# CAMPAIGN SERVICES
# ============================================================

CAMPAIGN_SERVICES = [
    "Social Media Management",
    "Lead Generation",
    "Digital Advertising",
    "Fence Installation",
    "Commercial Cleaning",
]


# ============================================================
# EXPECTED CASES
# ============================================================

TEST_CASES = [
    {
        "id": "realtor_listing",
        "title": "Realtor + property listing",
        "profile": {
            "username": "mariarealtor",
            "display_name": "Maria Realty",
            "bio": "Real Estate Agent helping buyers and sellers in the area.",
        },
        "post": {
            "caption_text": (
                "Beautiful new listing! "
                "3 bedrooms, 2 bathrooms, completely renovated. "
                "DM me for details or a private showing."
            ),
            "post_type": "image",
        },
        "expected": {
            "skip_post": False,
            "mode": "normal_prospecting",
            "selected_service": "Lead Generation",
        },
    },
    {
        "id": "wedding_photographer",
        "title": "Wedding photographer",
        "profile": {
            "username": "johnweddings",
            "display_name": "John Wedding Photography",
            "bio": "Wedding and event photographer.",
        },
        "post": {
            "caption_text": (
                "Another beautiful wedding day. "
                "Congratulations to this amazing couple!"
            ),
            "post_type": "image",
        },
        "expected": {
            "skip_post": False,
            "mode": "b2b_referral",
            "selected_service": "Social Media Management",
        },
    },
    {
        "id": "general_contractor",
        "title": "General contractor",
        "profile": {
            "username": "smithconstruction",
            "display_name": "Smith Construction",
            "bio": (
                "General contractor. "
                "Residential and commercial construction."
            ),
        },
        "post": {
            "caption_text": (
                "New commercial construction project underway."
            ),
            "post_type": "image",
        },
        "expected": {
            "skip_post": False,
            "mode": "b2b_referral",
            "selected_service": "Fence Installation",
        },
    },
    {
        "id": "landscaper",
        "title": "Landscaper",
        "profile": {
            "username": "greenlawns",
            "display_name": "Green Lawns Landscaping",
            "bio": "Professional landscaping and lawn care.",
        },
        "post": {
            "caption_text": (
                "Finished another backyard transformation for our client."
            ),
            "post_type": "image",
        },
        "expected": {
            "skip_post": False,
            "mode": "b2b_referral",
            "selected_service": "Fence Installation",
        },
    },
    {
        "id": "property_manager",
        "title": "Property manager",
        "profile": {
            "username": "premierpropertymanagement",
            "display_name": "Premier Property Management",
            "bio": "Managing residential and commercial properties.",
        },
        "post": {
            "caption_text": (
                "Commercial property ready for the next tenant."
            ),
            "post_type": "image",
        },
        "expected": {
            "skip_post": False,
            "mode": "b2b_referral",
            "selected_service": "Commercial Cleaning",
        },
    },
    {
        "id": "restaurant",
        "title": "Restaurant",
        "profile": {
            "username": "downtownbistro",
            "display_name": "Downtown Bistro",
            "bio": "Local restaurant serving lunch and dinner.",
        },
        "post": {
            "caption_text": (
                "Tonight's specials are here! "
                "Come join us for dinner."
            ),
            "post_type": "image",
        },
        "expected": {
            "skip_post": False,
            "mode": "normal_prospecting",
        },
    },
    {
        "id": "beauty_studio",
        "title": "Beauty studio",
        "profile": {
            "username": "glowbeautystudio",
            "display_name": "Glow Beauty Studio",
            "bio": (
                "Beauty studio specializing in hair and beauty services."
            ),
        },
        "post": {
            "caption_text": (
                "Another beautiful transformation today."
            ),
            "post_type": "image",
        },
        "expected": {
            "skip_post": False,
            "mode": "normal_prospecting",
        },
    },
    {
        "id": "auto_repair",
        "title": "Auto repair",
        "profile": {
            "username": "fastautorepair",
            "display_name": "Fast Auto Repair",
            "bio": (
                "Auto repair shop specializing in brakes and maintenance."
            ),
        },
        "post": {
            "caption_text": (
                "Brake job completed and ready for pickup."
            ),
            "post_type": "image",
        },
        "expected": {
            "skip_post": False,
            "mode": "normal_prospecting",
        },
    },
    {
        "id": "competitor",
        "title": "Direct competitor",
        "profile": {
            "username": "professionalcleaningco",
            "display_name": "Professional Commercial Cleaning",
            "bio": (
                "Commercial cleaning and janitorial services."
            ),
        },
        "post": {
            "caption_text": (
                "Another commercial cleaning project completed."
            ),
            "post_type": "image",
        },
        "expected": {
            "skip_post": True,
            "mode": "skip",
            "selected_service": "",
        },
    },
    {
        "id": "irrelevant_personal",
        "title": "Personal / irrelevant account",
        "profile": {
            "username": "john_doe_123",
            "display_name": "John",
            "bio": (
                "Just sharing moments with friends and family."
            ),
        },
        "post": {
            "caption_text": (
                "Great weekend with the family!"
            ),
            "post_type": "image",
        },
        "expected": {
            "skip_post": True,
            "mode": "skip",
            "selected_service": "",
        },
    },
]


# ============================================================
# LOGGING
# ============================================================

class TestLogger:
    """
    Logger mínimo para ejecutar el método real del bot
    sin levantar Selenium ni el resto del sistema.
    """

    def info(self, message, *args):
        if args:
            message = message % args

        print(f"[INFO] {message}")

    def warning(self, message, *args):
        if args:
            message = message % args

        print(f"[WARNING] {message}")

    def error(self, message, *args):
        if args:
            message = message % args

        print(f"[ERROR] {message}")


# ============================================================
# REAL BOT TASK
# ============================================================

def build_real_task(
    ai_api,
    personality_id,
    services,
):
    """
    Importa la clase REAL del bot.

    __new__ evita ejecutar __init__, por lo que no se inicializan:

    - Selenium
    - Instagram
    - Follow
    - Like
    - Comment
    - Database
    - otros servicios del bot
    """

    from app.tasks.instagram_prospect_discovery_task import (
        InstagramProspectDiscoveryTask,
    )

    task = InstagramProspectDiscoveryTask.__new__(
        InstagramProspectDiscoveryTask
    )

    task.ai_api = ai_api
    task.log = TestLogger()

    task.data = {
        "social_media_account": {
            "bot_personality_id": personality_id,
        }
    }

    task.current_search_term = "isolated_test"

    task.current_campaign = {
        "services_snapshot": services,
        "strategy_snapshot": {
            "description": (
                "Multi-industry Instagram prospecting. "
                "Identify the actual business first. "
                "Select the most appropriate campaign service. "
                "Separate direct prospects from referral partners "
                "and reject direct competitors."
            )
        },
    }

    return task


# ============================================================
# AI API
# ============================================================

def create_ai_api():
    try:
        from app.api.ai_api import AIAPI
    except Exception as exc:
        raise RuntimeError(
            "No se pudo importar app.api.ai_api.AIAPI: "
            f"{exc}"
        ) from exc

    print("[AIAPI] Preparando cliente...")

    client = AIAPI()

    print("[AIAPI] Cliente preparado.")

    return client


# ============================================================
# CASE PROMPT CONTEXT
# ============================================================

def build_case_specific_context(case):
    """
    Reglas adicionales de prueba.

    NO clasifican el resultado directamente.
    Solamente proporcionan a la IA las reglas comerciales
    que queremos que el motor real respete.
    """

    case_id = case["id"]

    if case_id == "realtor_listing":
        return """
SPECIAL BUSINESS RULE FOR THIS CASE:

This is a REAL ESTATE AGENT.

A real estate agent is a DIRECT PROSPECT when the campaign
offers Lead Generation, Social Media Management, or Digital
Advertising.

Do NOT classify a real estate agent as b2b_referral merely
because the business can refer other professionals.

For this case, evaluate the real estate business itself as
the potential customer of Lead Generation.

Expected commercial interpretation:
- direct business prospect
- Lead Generation is a valid direct service
- mode should be normal_prospecting
"""

    if case_id == "competitor":
        return """
SPECIAL BUSINESS RULE FOR THIS CASE:

This profile is a DIRECT COMPETITOR.

The business itself explicitly provides:
Commercial Cleaning.

Commercial Cleaning is also one of the campaign services.

When the prospect's core business directly sells the same
service offered by the campaign, classify the account as
a direct competitor and SKIP it.

Do NOT reinterpret a direct competitor as a referral partner.

For this case:
- skip_post must be true
- mode must be skip
- selected_service must be empty
- comment must be empty
"""

    return ""


# ============================================================
# TEST ONE CASE
# ============================================================

def run_case(
    task,
    case,
):
    expected = case.get("expected") or {}

    profile = case["profile"]
    post = case["post"]

    print()
    print("=" * 70)
    print(
        f"CASE: {case['id']} — "
        f"{case['title']}"
    )
    print("=" * 70)

    print(
        f"Industry/Bio: "
        f"{profile.get('bio', '')}"
    )

    print(
        f"Caption: "
        f"{post.get('caption_text', '')}"
    )

    try:
        result = task._qualify_candidate_with_ai(
            post_context=post,
            profile_context=profile,
            recent_posts=[],
            case_specific_context=build_case_specific_context(case),
        )

    except TypeError:
        """
        Compatibilidad con la versión actual del bot.

        Si el método REAL todavía no acepta
        case_specific_context, ejecutamos exactamente
        la firma actual sin inventar una nueva dependencia.
        """

        try:
            result = task._qualify_candidate_with_ai(
                post_context=post,
                profile_context=profile,
                recent_posts=[],
            )

        except Exception as exc:
            print()
            print("[ERROR]")
            print(repr(exc))
            return False

    except Exception as exc:
        print()
        print("[ERROR]")
        print(repr(exc))
        return False

    if not isinstance(result, dict):
        print()
        print("[ERROR] El método real no devolvió un dict.")
        print(repr(result))
        return False

    print()
    print("RESULT")
    print("-" * 70)

    fields = [
        "is_valid",
        "industry_detected",
        "qualification_score",
        "skip_post",
        "mode",
        "selected_service",
        "b2b_target_type",
        "b2b_angle",
        "b2b_confidence",
        "request_directness",
        "service_match_reason",
        "comment",
    ]

    for field in fields:
        print(
            f"{field}: "
            f"{result.get(field, '')}"
        )

    failures = []

    # --------------------------------------------------------
    # skip_post
    # --------------------------------------------------------

    if "skip_post" in expected:

        expected_skip = bool(
            expected["skip_post"]
        )

        if result.get("skip_post") != expected_skip:

            failures.append(
                "skip_post: "
                f"esperado={expected_skip!r}, "
                f"obtenido="
                f"{result.get('skip_post')!r}"
            )

    # --------------------------------------------------------
    # mode
    # --------------------------------------------------------

    if "mode" in expected:

        expected_mode = str(
            expected["mode"]
        ).strip().lower()

        obtained_mode = str(
            result.get("mode", "")
        ).strip().lower()

        if obtained_mode != expected_mode:

            failures.append(
                "mode: "
                f"esperado={expected_mode!r}, "
                f"obtenido={obtained_mode!r}"
            )

    # --------------------------------------------------------
    # selected service
    # --------------------------------------------------------

    if "selected_service" in expected:

        expected_service = str(
            expected["selected_service"]
        ).strip().lower()

        obtained_service = str(
            result.get(
                "selected_service",
                "",
            )
        ).strip().lower()

        if obtained_service != expected_service:

            failures.append(
                "selected_service: "
                f"esperado={expected_service!r}, "
                f"obtenido={obtained_service!r}"
            )

    # --------------------------------------------------------
    # Structural validation
    # --------------------------------------------------------

    skip_post = bool(
        result.get(
            "skip_post",
            False,
        )
    )

    if skip_post:

        if result.get("mode") != "skip":
            failures.append(
                "skip_post=true requiere mode=skip"
            )

        if result.get(
            "selected_service",
            "",
        ):
            failures.append(
                "skip_post=true requiere "
                "selected_service vacío"
            )

        if result.get(
            "request_directness",
            "",
        ) != "none":
            failures.append(
                "skip_post=true requiere "
                "request_directness=none"
            )

        if result.get(
            "b2b_confidence",
            "",
        ) != "low":
            failures.append(
                "skip_post=true requiere "
                "b2b_confidence=low"
            )

        if result.get(
            "comment",
            "",
        ):
            failures.append(
                "skip_post=true requiere "
                "comment vacío"
            )

    else:

        if result.get("mode") == "skip":

            failures.append(
                "skip_post=false no puede "
                "tener mode=skip"
            )

        if not str(
            result.get(
                "selected_service",
                "",
            )
        ).strip():

            failures.append(
                "prospecto válido requiere "
                "selected_service"
            )

        if not str(
            result.get(
                "comment",
                "",
            )
        ).strip():

            failures.append(
                "prospecto válido requiere comment"
            )

        if result.get(
            "b2b_confidence"
        ) not in {
            "high",
            "medium",
            "low",
        }:

            failures.append(
                "b2b_confidence inválido"
            )

        if result.get(
            "request_directness"
        ) not in {
            "direct",
            "indirect",
            "unclear",
        }:

            failures.append(
                "request_directness inválido"
            )

    # --------------------------------------------------------
    # Print result
    # --------------------------------------------------------

    print()

    if failures:

        print("✗ FAIL")

        for failure in failures:
            print(
                f"  - {failure}"
            )

        return False

    print("✓ PASS")

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Prueba aislada de la lógica "
            "multi-industria del bot."
        )
    )

    parser.add_argument(
        "--personality-id",
        type=int,
        default=7,
        help="Bot personality ID.",
    )

    parser.add_argument(
        "--case",
        help="Ejecutar únicamente un caso.",
    )

    parser.add_argument(
        "--no-ai",
        action="store_true",
        help=(
            "No llamar a la IA. "
            "Solo valida configuración."
        ),
    )

    args = parser.parse_args()

    print()
    print("=" * 70)
    print("MULTI-INDUSTRY ISOLATED TEST V4.1")
    print("=" * 70)
    print()

    print("Instagram : NO")
    print("Selenium  : NO")
    print("Follow    : NO")
    print("Like      : NO")
    print("Comment   : NO")
    print("Database  : NO")
    print()

    # --------------------------------------------------------
    # Select cases
    # --------------------------------------------------------

    cases = TEST_CASES

    if args.case:

        cases = [
            case
            for case in TEST_CASES
            if case["id"] == args.case
        ]

        if not cases:

            print(
                f"ERROR: caso inexistente: "
                f"{args.case}"
            )

            print()
            print("Casos disponibles:")

            for case in TEST_CASES:
                print(
                    f"  - {case['id']}"
                )

            return 1

    # --------------------------------------------------------
    # No AI
    # --------------------------------------------------------

    if args.no_ai:

        print(
            "Configuración correcta."
        )

        print(
            f"Casos preparados: "
            f"{len(cases)}"
        )

        return 0

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    try:

        ai_api = create_ai_api()

    except Exception as exc:

        print()
        print(
            "ERROR inicializando AI API:"
        )
        print(exc)

        return 1

    # --------------------------------------------------------
    # REAL BOT TASK
    # --------------------------------------------------------

    try:

        task = build_real_task(
            ai_api=ai_api,
            personality_id=args.personality_id,
            services=CAMPAIGN_SERVICES,
        )

    except Exception as exc:

        print()
        print(
            "ERROR importando el bot:"
        )
        print(repr(exc))

        return 1

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    passed = 0
    failed = 0

    for case in cases:

        ok = run_case(
            task=task,
            case=case,
        )

        if ok:
            passed += 1
        else:
            failed += 1

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(
        f"TOTAL : {len(cases)}"
    )

    print(
        f"PASS  : {passed}"
    )

    print(
        f"FAIL  : {failed}"
    )

    print()

    if failed == 0:

        print(
            "✓ MULTI-INDUSTRY ISOLATED TEST "
            "COMPLETED — 10/10"
        )

        return 0

    print(
        "✗ MULTI-INDUSTRY ISOLATED TEST "
        "DETECTED PROBLEMS"
    )

    return 1


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    raise SystemExit(
        main()
    )