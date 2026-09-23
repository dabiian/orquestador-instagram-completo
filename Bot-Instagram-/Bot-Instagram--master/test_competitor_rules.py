from app.services.instagram_prospect_classification_service import (
    InstagramProspectClassificationService,
)


class DummyAI:
    pass


def main():

    service = InstagramProspectClassificationService(
        ai_api=DummyAI()
    )

    industries = [
        "cleaning",
        "fences",
        "botanica",
        "spa",
        "spa colombia",
        "abogados",
        "marketing",
    ]

    print("=" * 80)
    print("TEST DE CARGA DE REGLAS POR INDUSTRIA")
    print("=" * 80)

    for industry in industries:

        print()
        print("-" * 80)
        print(f"INDUSTRIA: {industry}")
        print("-" * 80)

        rules = service.load_competitor_rules(industry)

        if not rules:
            print("ERROR: reglas vacías o no encontradas")
            continue

        print("OK: reglas cargadas")

        print(
            "industry:",
            rules.get("industry")
        )

        print(
            "core_services:",
            rules.get("core_services")
        )

        print(
            "direct_competitor_signals:",
            rules.get("direct_competitor_signals")
        )

        print(
            "possible_competitor_signals:",
            rules.get("possible_competitor_signals")
        )

        print(
            "adjacent_businesses:",
            rules.get("adjacent_businesses")
        )

        print(
            "referral_opportunities:",
            rules.get("referral_opportunities")
        )


if __name__ == "__main__":
    main()