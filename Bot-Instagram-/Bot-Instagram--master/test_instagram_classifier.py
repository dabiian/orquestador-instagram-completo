import json

from app.services.instagram_prospect_classification_service import (
    InstagramProspectClassificationService,
)


class TestLogger:
    def info(self, message, *args):
        print("[INFO]", message % args if args else message)

    def warning(self, message, *args):
        print("[WARNING]", message % args if args else message)


class TestAI:
    def get_bot_ia_long_prompt(self, bot_personality_id, prompt):
        print("\n" + "=" * 80)
        print("BOT PERSONALITY ID:")
        print(bot_personality_id)

        print("\n" + "=" * 80)
        print("PROMPT ENVIADO A LA IA:")
        print("=" * 80)
        print(prompt)
        print("=" * 80)

        # RESPUESTA CONTROLADA TEMPORALMENTE
        # Esto permite probar parser + normalización
        # SIN llamar realmente a la IA.
        response = {
            "competitor_score": 15,
            "is_competitor": False,
            "is_blacklisted": False,
            "blacklist_reason": "",
            "profile_classification": "LOCAL_BUSINESS_PAGE",
            "business_role": "COMPANY_PAGE",
            "business_vertical": "REAL_ESTATE",
            "competitor_relation": "ADJACENT_LOCAL_SERVICE",
            "is_direct_customer": False,
            "is_b2b_referral": True,
            "commercial_intent_score": 90,
            "classification_confidence": 94,
            "classification_evidence": [
                "El perfil representa una empresa de administración de propiedades.",
                "El negocio administra propiedades comerciales y edificios de apartamentos.",
                "No se identifica que el negocio proporcione servicios de limpieza comercial.",
                "La administración de propiedades puede relacionarse comercialmente con proveedores de servicios para edificios."
            ],
            "industry_detected": "cleaning"
            }

        return True, json.dumps(response)


def main():

    print("\n")
    print("=" * 80)
    print("TEST AISLADO - INSTAGRAM PROSPECT CLASSIFICATION SERVICE")
    print("=" * 80)

    ai_api = TestAI()
    logger = TestLogger()

    classifier = InstagramProspectClassificationService(
        ai_api=ai_api,
        logger=logger,
    )

    campaign = {
        "id": 123,
        "name": "Test Campaign",
        "campaign_type": "cleaning",
        "services_snapshot": [
            "Commercial Cleaning",
            "Lead Generation",
            "Social Media Management",
        ],
        "strategy_snapshot": {
            "industry": "cleaning",
            "hashtags": [
                "#commercialcleaning",
                "#chicago",
            ],
        },
    }

    profile_context = {
        "username": "chicago_commercial_cleaning",
        "display_name": "Chicago Commercial Cleaning",
        "bio": "Professional commercial cleaning and janitorial services.",
        "profile_url": "https://www.instagram.com/chicago_commercial_cleaning/",
    }

    post_context = {
        "post_url": "https://www.instagram.com/p/TEST456/",
        "post_type": "post",
        "caption_text": "Managing commercial properties and helping property owners maintain their buildings.",
    }

    recent_posts = [
        {
            "post_url": "https://www.instagram.com/p/RECENT1/",
            "caption_text": "Managing office buildings for commercial property owners.",
            "post_type": "post",
        },
        {
            "post_url": "https://www.instagram.com/p/RECENT2/",
            "caption_text": "Helping property owners coordinate maintenance and building services.",
            "post_type": "post",
        },
    ]

    print("\nEjecutando classify()...\n")

    ok, result = classifier.classify(
        bot_personality_id=1,
        campaign=campaign,
        profile_context=profile_context,
        post_context=post_context,
        recent_posts=recent_posts,
    )

    print("\n")
    print("=" * 80)
    print("RESULTADO")
    print("=" * 80)

    print("OK:", ok)

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n")
    print("=" * 80)
    print("VERIFICACIONES")
    print("=" * 80)

    print(
        "industry_detected:",
        result.get("industry_detected"),
    )

    print(
        "profile_classification:",
        result.get("profile_classification"),
    )

    print(
        "business_role:",
        result.get("business_role"),
    )

    print(
        "business_vertical:",
        result.get("business_vertical"),
    )

    print(
        "competitor_relation:",
        result.get("competitor_relation"),
    )

    print(
        "commercial_intent_score:",
        result.get("commercial_intent_score"),
    )

    print(
        "classification_confidence:",
        result.get("classification_confidence"),
    )

    print(
        "classification_evidence:",
        result.get("classification_evidence"),
    )


if __name__ == "__main__":
    main()