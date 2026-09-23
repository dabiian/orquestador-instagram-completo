import json
from pathlib import Path


# ============================================================
# IMPORTAR SERVICIO REAL
# ============================================================

try:
    from app.services.instagram_prospect_classification_service import (
        InstagramProspectClassificationService,
    )
except ImportError:
    from app.services.instagram_prospect_classification_service import (
        InstagramProspectClassificationService,
    )


# ============================================================
# FAKE AI
# ============================================================

class FakeAI:
    """
    Simula la IA.

    Sirve para comprobar que classify():
    - llama a la IA cuando corresponde
    - NO llama a la IA para competidores obvios
    """

    def __init__(self):
        self.calls = 0
        self.prompts = []

    def get_bot_ia_long_prompt(self, bot_personality_id, prompt):

        self.calls += 1
        self.prompts.append(prompt)

        response = {
            "competitor_score": 10,
            "is_competitor": False,
            "is_blacklisted": False,
            "blacklist_reason": "",
            "profile_classification": "LOCAL_BUSINESS_PAGE",
            "business_role": "COMPANY_PAGE",
            "business_vertical": "OTHER_SERVICE",
            "competitor_relation": "ADJACENT_LOCAL_SERVICE",
            "commercial_intent_score": 85,
            "classification_confidence": 95,
            "classification_evidence": [
                "FakeAI: negocio complementario detectado.",
                "FakeAI: no ofrece directamente el servicio principal de campaña.",
            ],
            "industry_detected": "unknown",
        }

        return True, json.dumps(response, ensure_ascii=False)


# ============================================================
# CAMPAÑAS DE PRUEBA
# ============================================================

def make_campaign(industry, services):

    return {
        "id": 999,
        "name": f"TEST {industry}",
        "campaign_type": industry,
        "industry": industry,
        "services_snapshot": services,
        "strategy_snapshot": {
            "industry": industry,
            "hashtags": [],
        },
    }


# ============================================================
# CASOS
# ============================================================

TEST_CASES = [

    # --------------------------------------------------------
    # COMPETIDORES
    # --------------------------------------------------------

    {
        "name": "Cleaning competitor",
        "industry": "cleaning",
        "services": [
            "Commercial Cleaning",
            "Lead Generation",
            "Social Media Management",
        ],
        "profile": {
            "username": "chicago_commercial_cleaning",
            "display_name": "Chicago Commercial Cleaning",
            "bio": "Professional commercial cleaning and janitorial services.",
        },
        "expected_competitor": True,
        "expected_ai_calls": 0,
    },

    {
        "name": "Fences competitor",
        "industry": "fences",
        "services": [
            "Fence Installation",
        ],
        "profile": {
            "username": "chicago_fence_installation",
            "display_name": "Chicago Fence Installation",
            "bio": "Residential and commercial fence installation.",
        },
        "expected_competitor": True,
        "expected_ai_calls": 0,
    },

    {
        "name": "Botanica competitor",
        "industry": "botanica",
        "services": [
            "Botanica",
            "Spiritual Products",
        ],
        "profile": {
            "username": "chicago_botanica",
            "display_name": "Chicago Botanica",
            "bio": "Botanica spiritual products and ritual supplies.",
        },
        "expected_competitor": True,
        "expected_ai_calls": 0,
    },

    {
        "name": "Spa competitor",
        "industry": "spa",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": {
            "username": "chicago_day_spa",
            "display_name": "Chicago Day Spa",
            "bio": "Day spa offering massage, facials and beauty treatments.",
        },
        "expected_competitor": True,
        "expected_ai_calls": 0,
    },

    {
        "name": "Spa Colombia competitor",
        "industry": "spa colombia",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": {
            "username": "spa_colombia",
            "display_name": "Spa Colombia",
            "bio": "Spa, massage and beauty treatments.",
        },
        "expected_competitor": True,
        "expected_ai_calls": 0,
    },

    {
        "name": "Abogados competitor",
        "industry": "abogados",
        "services": [
            "Legal Services",
            "Legal Representation",
        ],
        "profile": {
            "username": "chicago_law_firm",
            "display_name": "Chicago Law Firm",
            "bio": "Law firm providing legal services and legal representation.",
        },
        "expected_competitor": True,
        "expected_ai_calls": 0,
    },

    {
        "name": "Marketing competitor",
        "industry": "marketing",
        "services": [
            "Digital Marketing",
            "Social Media Management",
            "Lead Generation",
        ],
        "profile": {
            "username": "chicago_digital_marketing",
            "display_name": "Chicago Digital Marketing",
            "bio": "Digital marketing agency offering social media management.",
        },
        "expected_competitor": True,
        "expected_ai_calls": 0,
    },

    # --------------------------------------------------------
    # NO COMPETIDORES
    # --------------------------------------------------------

    {
        "name": "Cleaning adjacent",
        "industry": "cleaning",
        "services": [
            "Commercial Cleaning",
            "Lead Generation",
            "Social Media Management",
        ],
        "profile": {
            "username": "chicago_property_management",
            "display_name": "Chicago Property Management",
            "bio": "We manage commercial properties and apartment buildings for property owners.",
        },
        "expected_competitor": False,
        "expected_ai_calls": 1,
    },

    {
        "name": "Fences adjacent",
        "industry": "fences",
        "services": [
            "Fence Installation",
        ],
        "profile": {
            "username": "chicago_landscaping",
            "display_name": "Chicago Landscaping",
            "bio": "Professional landscaping and outdoor property services.",
        },
        "expected_competitor": False,
        "expected_ai_calls": 1,
    },

    {
        "name": "Botanica adjacent",
        "industry": "botanica",
        "services": [
            "Botanica",
            "Spiritual Products",
        ],
        "profile": {
            "username": "chicago_wellness",
            "display_name": "Chicago Wellness",
            "bio": "Wellness studio offering yoga and holistic wellness services.",
        },
        "expected_competitor": False,
        "expected_ai_calls": 1,
    },

    {
        "name": "Spa adjacent",
        "industry": "spa",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": {
            "username": "chicago_fitness",
            "display_name": "Chicago Fitness",
            "bio": "Fitness studio helping clients improve strength and wellness.",
        },
        "expected_competitor": False,
        "expected_ai_calls": 1,
    },

    {
        "name": "Spa Colombia adjacent",
        "industry": "spa colombia",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": {
            "username": "hotel_colombia",
            "display_name": "Hotel Colombia",
            "bio": "Hotel offering accommodation and guest services.",
        },
        "expected_competitor": False,
        "expected_ai_calls": 1,
    },

    {
        "name": "Abogados adjacent",
        "industry": "abogados",
        "services": [
            "Legal Services",
            "Legal Representation",
        ],
        "profile": {
            "username": "chicago_accounting",
            "display_name": "Chicago Accounting",
            "bio": "Accounting and tax services for local businesses.",
        },
        "expected_competitor": False,
        "expected_ai_calls": 1,
    },

    {
        "name": "Marketing adjacent",
        "industry": "marketing",
        "services": [
            "Digital Marketing",
            "Social Media Management",
            "Lead Generation",
        ],
        "profile": {
            "username": "chicago_web_design",
            "display_name": "Chicago Web Design",
            "bio": "Web design and website development services.",
        },
        "expected_competitor": False,
        "expected_ai_calls": 1,
    },
]


# ============================================================
# EJECUTAR TEST
# ============================================================

def main():

    print("=" * 80)
    print("TEST DE INTEGRACIÓN COMPLETA - INSTAGRAM CLASSIFIER")
    print("=" * 80)
    print()
    print("Este test comprueba:")
    print("  1. Detección de industria")
    print("  2. Carga de reglas")
    print("  3. Detección determinística de competidores")
    print("  4. Cortocircuito antes de la IA")
    print("  5. Ejecución de IA para no competidores")
    print("  6. Parseo de respuesta")
    print("  7. Normalización del resultado")
    print()

    fake_ai = FakeAI()

    service = InstagramProspectClassificationService(
        ai_api=fake_ai,
        logger=None,
    )

    total = len(TEST_CASES)
    passed = 0
    failed = 0

    print("=" * 80)

    for index, case in enumerate(TEST_CASES, start=1):

        print("-" * 80)
        print(f"TEST {index}/{total}")
        print(f"Nombre: {case['name']}")
        print(f"Industria: {case['industry']}")
        print(f"Perfil: @{case['profile']['username']}")
        print(
            f"Esperado: "
            f"{'COMPETIDOR' if case['expected_competitor'] else 'NO COMPETIDOR'}"
        )

        # ----------------------------------------------------
        # RESET FAKE AI
        # ----------------------------------------------------

        fake_ai.calls = 0
        fake_ai.prompts = []

        # ----------------------------------------------------
        # CAMPAÑA
        # ----------------------------------------------------

        campaign = make_campaign(
            industry=case["industry"],
            services=case["services"],
        )

        # ----------------------------------------------------
        # POST
        # ----------------------------------------------------

        post_context = {
            "post_url": "https://www.instagram.com/p/TEST/",
            "post_type": "post",
            "caption_text": case["profile"]["bio"],
        }

        # ----------------------------------------------------
        # RECENT POSTS
        # ----------------------------------------------------

        recent_posts = [
            {
                "post_url": "https://www.instagram.com/p/RECENT1/",
                "caption_text": case["profile"]["bio"],
                "post_type": "post",
            }
        ]

        # ----------------------------------------------------
        # CLASSIFY
        # ----------------------------------------------------

        try:

            ok, result = service.classify(
                bot_personality_id=1,
                campaign=campaign,
                profile_context=case["profile"],
                post_context=post_context,
                recent_posts=recent_posts,
            )

        except Exception as exc:

            print(f"❌ EXCEPTION: {exc}")
            failed += 1
            continue

        # ----------------------------------------------------
        # VERIFICACIONES
        # ----------------------------------------------------

        test_ok = True

        # classify() debe terminar correctamente
        if not ok:

            print("❌ classify() devolvió OK=False")
            print(f"   Resultado: {result}")
            test_ok = False

        else:

            print("✓ classify() OK")

        # ----------------------------------------------------
        # INDUSTRIA
        # ----------------------------------------------------

        target_industry = result.get("industry_target")
        detected_industry = result.get("industry_detected")

        if target_industry == case["industry"]:
            print(f"✓ Industria objetivo correcta: {target_industry}")
            print(f"  Industria detectada del perfil: {detected_industry}")
        else:
            print(
                f"❌ Industria objetivo incorrecta:"
                f" esperada={case['industry']}"
                f" target={target_industry}"
            )
            test_ok = False

        # ----------------------------------------------------
        # COMPETIDOR
        # ----------------------------------------------------

        detected_competitor = bool(
            result.get("is_competitor")
        )

        print(
            "✓" if detected_competitor == case["expected_competitor"]
            else "❌",
            "Competidor:",
            "COMPETIDOR" if detected_competitor else "NO COMPETIDOR",
        )

        if detected_competitor != case["expected_competitor"]:

            test_ok = False

        # ----------------------------------------------------
        # BLACKLIST
        # ----------------------------------------------------

        blacklisted = bool(
            result.get("is_blacklisted")
        )

        if case["expected_competitor"]:

            if blacklisted:

                print("✓ Blacklist correcta")

            else:

                print("❌ Competidor no quedó blacklisted")
                test_ok = False

        else:

            if not blacklisted:

                print("✓ No quedó blacklisted")

            else:

                print("❌ Falso positivo de blacklist")
                test_ok = False

        # ----------------------------------------------------
        # RELACIÓN
        # ----------------------------------------------------

        relation = result.get(
            "competitor_relation"
        )

        print(
            f"✓ competitor_relation: {relation}"
        )

        # ----------------------------------------------------
        # LLAMADAS A IA
        # ----------------------------------------------------

        ai_calls = fake_ai.calls

        expected_ai_calls = case[
            "expected_ai_calls"
        ]

        if ai_calls == expected_ai_calls:

            print(
                f"✓ Llamadas a IA: {ai_calls}"
            )

        else:

            print(
                f"❌ Llamadas a IA incorrectas:"
                f" esperadas={expected_ai_calls}"
                f" realizadas={ai_calls}"
            )

            test_ok = False

        # ----------------------------------------------------
        # SI PASÓ POR IA
        # ----------------------------------------------------

        if expected_ai_calls == 1:

            if fake_ai.prompts:

                prompt = fake_ai.prompts[0]

                if case["industry"] in prompt:

                    print("✓ Prompt contiene la industria")

                else:

                    print("❌ Prompt no contiene la industria")
                    test_ok = False

                if "COMPETITOR RULES" in prompt:

                    print("✓ Prompt contiene COMPETITOR RULES")

                else:

                    print("❌ Prompt no contiene COMPETITOR RULES")
                    test_ok = False

            else:

                print("❌ No se generó prompt para la IA")
                test_ok = False

        # ----------------------------------------------------
        # RESULTADO NORMALIZADO
        # ----------------------------------------------------

        required_fields = [
            "competitor_score",
            "is_competitor",
            "is_blacklisted",
            "blacklist_reason",
            "profile_classification",
            "business_role",
            "business_vertical",
            "competitor_relation",
            "commercial_intent_score",
            "classification_confidence",
            "classification_evidence",
            "industry_detected",
        ]

        missing_fields = [
            field
            for field in required_fields
            if field not in result
        ]

        if not missing_fields:

            print("✓ Resultado normalizado completo")

        else:

            print(
                "❌ Faltan campos:",
                missing_fields,
            )

            test_ok = False

        # ----------------------------------------------------
        # RESULTADO DEL TEST
        # ----------------------------------------------------

        if test_ok:

            print()
            print("✓ PASS")
            passed += 1

        else:

            print()
            print("❌ FAIL")
            failed += 1

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
        print("✓ TODOS LOS TESTS DE INTEGRACIÓN PASARON")
        print("=" * 80)
        print()
        print("El flujo completo del Instagram classifier funciona.")
        print()
        print("Competidores:")
        print("  ✓ Detectados antes de llamar a la IA")
        print("  ✓ Marcados como blacklisted")
        print()
        print("No competidores:")
        print("  ✓ No son marcados como competidores")
        print("  ✓ Continúan hacia la IA")
        print("  ✓ Reciben resultado normalizado")
        print()

    else:

        print("=" * 80)
        print("❌ HAY TESTS DE INTEGRACIÓN FALLANDO")
        print("=" * 80)
        print()
        print("NO hagamos cambios todavía.")
        print("Primero revisamos exactamente cuál test falló.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()