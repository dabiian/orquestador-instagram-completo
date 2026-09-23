from pathlib import Path
import sys


# ============================================================
# PERMITIR IMPORTAR app/
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from app.services.instagram_prospect_classification_service import (
    InstagramProspectClassificationService,
)


# ============================================================
# AI MOCK
# ============================================================

class FakeAI:
    """
    Este test NO llama a la IA.
    Solo necesitamos poder crear el servicio.
    """

    pass


# ============================================================
# LOGGER SIMPLE
# ============================================================

class FakeLogger:

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        print("[WARNING]", *args)


# ============================================================
# CREAR SERVICIO
# ============================================================

service = InstagramProspectClassificationService(
    ai_api=FakeAI(),
    logger=FakeLogger(),
)


# ============================================================
# CASOS DE PRUEBA
# ============================================================

TEST_CASES = [

    # ========================================================
    # CLEANING
    # ========================================================

    {
        "industry": "cleaning",

        "campaign": {
            "campaign_type": "cleaning",
            "industry": "cleaning",
            "services_snapshot": [
                "Commercial Cleaning",
                "Lead Generation",
                "Social Media Management",
            ],
        },

        "profile": {
            "username": "chicago_commercial_cleaning",
            "display_name": "Chicago Commercial Cleaning",
            "bio": (
                "Professional commercial cleaning "
                "and janitorial services."
            ),
        },

        "expected_competitor": True,
    },

    # ========================================================
    # FENCES
    # ========================================================

    {
        "industry": "fences",

        "campaign": {
            "campaign_type": "fences",
            "industry": "fences",
            "services_snapshot": [
                "Fence Installation",
                "Fence Repair",
            ],
        },

        "profile": {
            "username": "chicago_fence_installation",
            "display_name": "Chicago Fence Installation",
            "bio": (
                "Residential and commercial "
                "fence installation."
            ),
        },

        "expected_competitor": True,
    },

    # ========================================================
    # BOTANICA
    # ========================================================

    {
        "industry": "botanica",

        "campaign": {
            "campaign_type": "botanica",
            "industry": "botanica",
            "services_snapshot": [
                "Botanica",
                "Spiritual Products",
            ],
        },

        "profile": {
            "username": "chicago_botanica",
            "display_name": "Chicago Botanica",
            "bio": (
                "Botanica and spiritual products "
                "for rituals and spiritual practices."
            ),
        },

        "expected_competitor": True,
    },

    # ========================================================
    # SPA
    # ========================================================

    {
        "industry": "spa",

        "campaign": {
            "campaign_type": "spa",
            "industry": "spa",
            "services_snapshot": [
                "Spa",
                "Massage",
                "Facials",
            ],
        },

        "profile": {
            "username": "chicago_day_spa",
            "display_name": "Chicago Day Spa",
            "bio": (
                "Day spa offering massage, facials "
                "and wellness treatments."
            ),
        },

        "expected_competitor": True,
    },

    # ========================================================
    # SPA COLOMBIA
    # ========================================================

    {
        "industry": "spa colombia",

        "campaign": {
            "campaign_type": "spa colombia",
            "industry": "spa colombia",
            "services_snapshot": [
                "Spa",
                "Massage",
                "Facials",
            ],
        },

        "profile": {
            "username": "spa_colombia",
            "display_name": "Spa Colombia",
            "bio": (
                "Spa and wellness center offering "
                "massage, facials and beauty treatments."
            ),
        },

        "expected_competitor": True,
    },

    # ========================================================
    # ABOGADOS
    # ========================================================

    {
        "industry": "abogados",

        "campaign": {
            "campaign_type": "abogados",
            "industry": "abogados",
            "services_snapshot": [
                "Legal Services",
                "Legal Representation",
            ],
        },

        "profile": {
            "username": "chicago_law_firm",
            "display_name": "Chicago Law Firm",
            "bio": (
                "Law firm providing legal services "
                "and legal representation."
            ),
        },

        "expected_competitor": True,
    },

    # ========================================================
    # MARKETING
    # ========================================================

    {
        "industry": "marketing",

        "campaign": {
            "campaign_type": "marketing",
            "industry": "marketing",
            "services_snapshot": [
                "Digital Marketing",
                "Lead Generation",
                "Social Media Management",
            ],
        },

        "profile": {
            "username": "chicago_digital_marketing",
            "display_name": "Chicago Digital Marketing Agency",
            "bio": (
                "Digital marketing agency offering "
                "social media management and lead generation."
            ),
        },

        "expected_competitor": True,
    },


    # ========================================================
    # FALSOS POSITIVOS
    # ========================================================

    {
        "industry": "cleaning",

        "campaign": {
            "campaign_type": "cleaning",
            "industry": "cleaning",
            "services_snapshot": [
                "Commercial Cleaning",
                "Lead Generation",
                "Social Media Management",
            ],
        },

        "profile": {
            "username": "chicago_property_management",
            "display_name": "Chicago Property Management",
            "bio": (
                "We manage commercial properties "
                "and apartment buildings for property owners."
            ),
        },

        "expected_competitor": False,
    },

    {
        "industry": "fences",

        "campaign": {
            "campaign_type": "fences",
            "industry": "fences",
            "services_snapshot": [
                "Fence Installation",
                "Fence Repair",
            ],
        },

        "profile": {
            "username": "chicago_landscaping",
            "display_name": "Chicago Landscaping",
            "bio": (
                "Professional landscaping and "
                "outdoor maintenance services."
            ),
        },

        "expected_competitor": False,
    },

    {
        "industry": "marketing",

        "campaign": {
            "campaign_type": "marketing",
            "industry": "marketing",
            "services_snapshot": [
                "Digital Marketing",
                "Lead Generation",
                "Social Media Management",
            ],
        },

        "profile": {
            "username": "chicago_web_design",
            "display_name": "Chicago Web Design",
            "bio": (
                "We design modern websites "
                "for local businesses."
            ),
        },

        "expected_competitor": False,
    },
]


# ============================================================
# EJECUTAR TEST
# ============================================================

def main():

    print("=" * 80)
    print("TEST DE DETECCIÓN DE COMPETIDORES POR INDUSTRIA")
    print("=" * 80)

    print()
    print("Este test usa:")
    print("  detect_obvious_competitor()")
    print("  SIN llamar a la IA")
    print()

    total = len(TEST_CASES)
    passed = 0
    failed = 0

    for index, case in enumerate(TEST_CASES, start=1):

        industry = case["industry"]

        campaign = case["campaign"]
        profile = case["profile"]

        expected = case["expected_competitor"]

        print("-" * 80)

        print(
            f"TEST {index}/{total}"
        )

        print(
            f"Industria: {industry}"
        )

        print(
            f"Perfil: @{profile['username']}"
        )

        print(
            f"Esperado: "
            f"{'COMPETIDOR' if expected else 'NO COMPETIDOR'}"
        )

        # ----------------------------------------------------
        # EJECUTAR MÉTODO REAL
        # ----------------------------------------------------

        try:

            result = service.detect_obvious_competitor(
                campaign=campaign,
                profile_context=profile,
            )

        except Exception as exc:

            print()
            print("❌ ERROR EJECUTANDO TEST")
            print(
                f"   {type(exc).__name__}: {exc}"
            )

            failed += 1
            continue

        detected = result is not None

        print(
            f"Detectado: "
            f"{'COMPETIDOR' if detected else 'NO COMPETIDOR'}"
        )

        # ----------------------------------------------------
        # COMPARAR RESULTADO
        # ----------------------------------------------------

        if detected == expected:

            print("✓ PASS")

            passed += 1

        else:

            print("❌ FAIL")

            failed += 1

            if result:

                print()
                print("Resultado obtenido:")

                print(
                    f"  competitor_score: "
                    f"{result.get('competitor_score')}"
                )

                print(
                    f"  is_competitor: "
                    f"{result.get('is_competitor')}"
                )

                print(
                    f"  is_blacklisted: "
                    f"{result.get('is_blacklisted')}"
                )

                print(
                    f"  competitor_relation: "
                    f"{result.get('competitor_relation')}"
                )

    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    print()
    print("=" * 80)
    print("RESULTADO FINAL")
    print("=" * 80)

    print()
    print(f"Total tests: {total}")
    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")

    print()

    if failed == 0:

        print("=" * 80)
        print("✓ TODOS LOS TESTS PASARON")
        print("=" * 80)

        print()
        print(
            "La detección determinística de competencia "
            "está funcionando para los casos probados."
        )

        return 0

    print("=" * 80)
    print("❌ HAY TESTS QUE FALLARON")
    print("=" * 80)

    print()
    print(
        "NO cambies todavía los JSON."
    )

    print(
        "Primero revisemos qué caso específico falló."
    )

    return 1


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    raise SystemExit(
        main()
    )
