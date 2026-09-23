import json
import sys

from app.api.ai_api import AIAPI
from app.services.instagram_prospect_classification_service import (
    InstagramProspectClassificationService,
)


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

BOT_PERSONALITY_ID = 1


# ============================================================================
# HELPERS
# ============================================================================

def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def separator(char="=", length=80):
    print(char * length)


def make_campaign(industry, services):
    return {
        "id": 999,
        "name": f"Boundary Test - {industry}",
        "campaign_type": industry,
        "industry": industry,
        "services_snapshot": services,
        "strategy_snapshot": {
            "industry": industry,
            "hashtags": [],
        },
    }


def make_profile(username, display_name, bio):
    return {
        "username": username,
        "display_name": display_name,
        "bio": bio,
        "profile_url": f"https://www.instagram.com/{username}/",
    }


def make_post(caption):
    return {
        "post_url": "https://www.instagram.com/p/BOUNDARYTEST/",
        "post_type": "post",
        "caption_text": caption,
    }


# ============================================================================
# CASOS DE FRONTERA
#
# IMPORTANTE:
# Aquí NO asumimos que todos los casos adyacentes necesariamente tienen que
# producir ADJACENT_LOCAL_SERVICE.
#
# Queremos observar cómo clasifica la IA los casos:
#
#   - DIRECT_COMPETITOR
#   - ADJACENT_LOCAL_SERVICE
#   - UNRELATED_BUSINESS
#
# Los casos marcados como "FRONTERA" sirven para análisis humano.
# ============================================================================

CASES = [

    # ========================================================================
    # CLEANING
    # ========================================================================

    {
        "name": "Cleaning - competidor claro",
        "industry": "cleaning",
        "services": [
            "Commercial Cleaning",
            "Lead Generation",
            "Social Media Management",
        ],
        "profile": make_profile(
            "chicago_janitorial_services",
            "Chicago Janitorial Services",
            "Commercial cleaning, janitorial services and office cleaning "
            "for businesses in Chicago.",
        ),
        "post": make_post(
            "Professional commercial cleaning and janitorial services "
            "for Chicago businesses."
        ),
        "expected_type": "CLEAR_COMPETITOR",
    },

    {
        "name": "Cleaning - property management",
        "industry": "cleaning",
        "services": [
            "Commercial Cleaning",
            "Lead Generation",
            "Social Media Management",
        ],
        "profile": make_profile(
            "chicago_property_management",
            "Chicago Property Management",
            "We manage commercial properties and apartment buildings "
            "for property owners.",
        ),
        "post": make_post(
            "Managing office buildings for commercial property owners."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Cleaning - landscaping",
        "industry": "cleaning",
        "services": [
            "Commercial Cleaning",
            "Lead Generation",
            "Social Media Management",
        ],
        "profile": make_profile(
            "chicago_landscaping",
            "Chicago Landscaping",
            "Commercial landscaping, lawn care and outdoor property "
            "maintenance services.",
        ),
        "post": make_post(
            "Keeping commercial properties beautiful with professional "
            "landscaping and lawn care."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Cleaning - HVAC",
        "industry": "cleaning",
        "services": [
            "Commercial Cleaning",
            "Lead Generation",
            "Social Media Management",
        ],
        "profile": make_profile(
            "chicago_hvac",
            "Chicago HVAC",
            "Commercial heating, cooling and HVAC maintenance services.",
        ),
        "post": make_post(
            "HVAC installation and maintenance for Chicago businesses."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Cleaning - restaurant",
        "industry": "cleaning",
        "services": [
            "Commercial Cleaning",
            "Lead Generation",
            "Social Media Management",
        ],
        "profile": make_profile(
            "chicago_restaurant",
            "Chicago Restaurant",
            "Local restaurant serving burgers, sandwiches and drinks.",
        ),
        "post": make_post(
            "Come enjoy our burgers and lunch specials."
        ),
        "expected_type": "CLEAR_UNRELATED",
    },


    # ========================================================================
    # FENCES
    # ========================================================================

    {
        "name": "Fences - competidor claro",
        "industry": "fences",
        "services": [
            "Fence Installation",
            "Fence Repair",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_fence_contractor",
            "Chicago Fence Contractor",
            "Professional fence installation and fence repair "
            "for residential and commercial properties.",
        ),
        "post": make_post(
            "New wood fence installation completed in Chicago."
        ),
        "expected_type": "CLEAR_COMPETITOR",
    },

    {
        "name": "Fences - landscaping",
        "industry": "fences",
        "services": [
            "Fence Installation",
            "Fence Repair",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_landscaping",
            "Chicago Landscaping",
            "Professional landscaping, lawn care and outdoor property "
            "maintenance services.",
        ),
        "post": make_post(
            "Landscape maintenance for commercial properties in Chicago."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Fences - roofing",
        "industry": "fences",
        "services": [
            "Fence Installation",
            "Fence Repair",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_roofing",
            "Chicago Roofing",
            "Commercial and residential roofing installation and repair.",
        ),
        "post": make_post(
            "Roof replacement and roof repair for Chicago properties."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Fences - real estate",
        "industry": "fences",
        "services": [
            "Fence Installation",
            "Fence Repair",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_real_estate",
            "Chicago Real Estate",
            "Real estate company helping buyers and sellers "
            "with residential and commercial properties.",
        ),
        "post": make_post(
            "Commercial property available for sale in Chicago."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Fences - restaurant",
        "industry": "fences",
        "services": [
            "Fence Installation",
            "Fence Repair",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_restaurant",
            "Chicago Restaurant",
            "Local restaurant serving food and drinks.",
        ),
        "post": make_post(
            "Join us tonight for dinner."
        ),
        "expected_type": "CLEAR_UNRELATED",
    },


    # ========================================================================
    # BOTANICA
    # ========================================================================

    {
        "name": "Botanica - competidor claro",
        "industry": "botanica",
        "services": [
            "Botanica",
            "Spiritual Products",
            "Religious Products",
        ],
        "profile": make_profile(
            "chicago_botanica_shop",
            "Chicago Botanica",
            "Botanica offering spiritual products, candles, oils, "
            "herbs and religious items.",
        ),
        "post": make_post(
            "Spiritual candles, oils and botanica products available."
        ),
        "expected_type": "CLEAR_COMPETITOR",
    },

    {
        "name": "Botanica - wellness",
        "industry": "botanica",
        "services": [
            "Botanica",
            "Spiritual Products",
            "Religious Products",
        ],
        "profile": make_profile(
            "chicago_wellness",
            "Chicago Wellness",
            "Wellness center focused on healthy living, relaxation "
            "and personal wellbeing.",
        ),
        "post": make_post(
            "Wellness programs helping Chicago residents feel healthier."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Botanica - yoga",
        "industry": "botanica",
        "services": [
            "Botanica",
            "Spiritual Products",
            "Religious Products",
        ],
        "profile": make_profile(
            "chicago_yoga",
            "Chicago Yoga",
            "Yoga studio offering meditation, yoga classes "
            "and mindfulness programs.",
        ),
        "post": make_post(
            "Join our meditation and yoga classes this week."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Botanica - restaurant",
        "industry": "botanica",
        "services": [
            "Botanica",
            "Spiritual Products",
            "Religious Products",
        ],
        "profile": make_profile(
            "chicago_restaurant",
            "Chicago Restaurant",
            "Restaurant serving traditional food.",
        ),
        "post": make_post(
            "Fresh food and dinner specials every weekend."
        ),
        "expected_type": "CLEAR_UNRELATED",
    },


    # ========================================================================
    # SPA
    # ========================================================================

    {
        "name": "Spa - competidor claro",
        "industry": "spa",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": make_profile(
            "chicago_day_spa",
            "Chicago Day Spa",
            "Day spa offering massages, facials, skincare "
            "and relaxation treatments.",
        ),
        "post": make_post(
            "Book your massage and facial treatment today."
        ),
        "expected_type": "CLEAR_COMPETITOR",
    },

    {
        "name": "Spa - fitness",
        "industry": "spa",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": make_profile(
            "chicago_fitness",
            "Chicago Fitness",
            "Fitness center helping members stay healthy, active "
            "and strong.",
        ),
        "post": make_post(
            "Personal training and fitness programs for Chicago residents."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Spa - hotel",
        "industry": "spa",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": make_profile(
            "hotel_chicago",
            "Chicago Hotel",
            "Hotel providing accommodation, hospitality "
            "and guest services.",
        ),
        "post": make_post(
            "Comfortable rooms and hospitality services for travelers."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Spa - salon",
        "industry": "spa",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": make_profile(
            "chicago_salon",
            "Chicago Salon",
            "Hair salon offering haircuts, styling, coloring "
            "and beauty services.",
        ),
        "post": make_post(
            "New hair color and styling appointments available."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Spa - yoga",
        "industry": "spa",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": make_profile(
            "chicago_yoga",
            "Chicago Yoga",
            "Yoga and meditation studio focused on relaxation, "
            "mindfulness and wellbeing.",
        ),
        "post": make_post(
            "Meditation and yoga classes for relaxation and wellbeing."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Spa - restaurant",
        "industry": "spa",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": make_profile(
            "chicago_restaurant",
            "Chicago Restaurant",
            "Local restaurant serving food and drinks.",
        ),
        "post": make_post(
            "Dinner specials available this weekend."
        ),
        "expected_type": "CLEAR_UNRELATED",
    },


    # ========================================================================
    # SPA COLOMBIA
    # ========================================================================

    {
        "name": "Spa Colombia - competidor claro",
        "industry": "spa colombia",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": make_profile(
            "spa_colombia",
            "Spa Colombia",
            "Spa offering massages, facials, relaxation "
            "and beauty treatments in Colombia.",
        ),
        "post": make_post(
            "Book your massage and facial treatment in Colombia."
        ),
        "expected_type": "CLEAR_COMPETITOR",
    },

    {
        "name": "Spa Colombia - hotel",
        "industry": "spa colombia",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": make_profile(
            "hotel_colombia",
            "Hotel Colombia",
            "Hotel providing accommodation, hospitality "
            "and guest services for travelers.",
        ),
        "post": make_post(
            "Comfortable rooms and hospitality services for travelers."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Spa Colombia - wellness",
        "industry": "spa colombia",
        "services": [
            "Spa",
            "Massage",
            "Facials",
        ],
        "profile": make_profile(
            "colombia_wellness",
            "Colombia Wellness",
            "Wellness center offering relaxation, wellbeing "
            "and healthy lifestyle programs.",
        ),
        "post": make_post(
            "Wellness and relaxation programs in Colombia."
        ),
        "expected_type": "BOUNDARY",
    },


    # ========================================================================
    # ABOGADOS
    # ========================================================================

    {
        "name": "Abogados - competidor claro",
        "industry": "abogados",
        "services": [
            "Legal Services",
            "Business Law",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_law_firm",
            "Chicago Law Firm",
            "Law firm providing legal services for businesses "
            "and individuals in Chicago.",
        ),
        "post": make_post(
            "Contact our attorneys for a consultation."
        ),
        "expected_type": "CLEAR_COMPETITOR",
    },

    {
        "name": "Abogados - accounting",
        "industry": "abogados",
        "services": [
            "Legal Services",
            "Business Law",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_accounting",
            "Chicago Accounting",
            "Accounting firm providing bookkeeping, tax preparation "
            "and financial services for businesses.",
        ),
        "post": make_post(
            "Helping Chicago businesses with accounting and tax services."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Abogados - insurance",
        "industry": "abogados",
        "services": [
            "Legal Services",
            "Business Law",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_insurance",
            "Chicago Insurance",
            "Insurance agency helping businesses and families "
            "with commercial and personal insurance.",
        ),
        "post": make_post(
            "Commercial insurance solutions for Chicago businesses."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Abogados - restaurant",
        "industry": "abogados",
        "services": [
            "Legal Services",
            "Business Law",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_restaurant",
            "Chicago Restaurant",
            "Restaurant serving food and drinks.",
        ),
        "post": make_post(
            "Join us tonight for dinner."
        ),
        "expected_type": "CLEAR_UNRELATED",
    },


    # ========================================================================
    # MARKETING
    # ========================================================================

    {
        "name": "Marketing - competidor claro",
        "industry": "marketing",
        "services": [
            "Digital Marketing",
            "Social Media Management",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_digital_marketing",
            "Chicago Digital Marketing",
            "Digital marketing agency providing SEO, social media, "
            "advertising and lead generation.",
        ),
        "post": make_post(
            "Grow your business with our digital marketing services."
        ),
        "expected_type": "CLEAR_COMPETITOR",
    },

    {
        "name": "Marketing - web design",
        "industry": "marketing",
        "services": [
            "Digital Marketing",
            "Social Media Management",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_web_design",
            "Chicago Web Design",
            "Web design agency creating websites and online experiences "
            "for businesses.",
        ),
        "post": make_post(
            "Professional website design for Chicago businesses."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Marketing - branding",
        "industry": "marketing",
        "services": [
            "Digital Marketing",
            "Social Media Management",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_branding",
            "Chicago Branding",
            "Branding agency helping businesses develop their identity, "
            "visual systems and brand strategy.",
        ),
        "post": make_post(
            "Build a stronger brand identity for your business."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Marketing - PR",
        "industry": "marketing",
        "services": [
            "Digital Marketing",
            "Social Media Management",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_pr",
            "Chicago PR",
            "Public relations agency helping companies manage "
            "communications and media relations.",
        ),
        "post": make_post(
            "Public relations and media strategy for businesses."
        ),
        "expected_type": "BOUNDARY",
    },

    {
        "name": "Marketing - plumber",
        "industry": "marketing",
        "services": [
            "Digital Marketing",
            "Social Media Management",
            "Lead Generation",
        ],
        "profile": make_profile(
            "chicago_plumbing",
            "Chicago Plumbing",
            "Professional plumbing installation and repair services.",
        ),
        "post": make_post(
            "Emergency plumbing services available 24/7."
        ),
        "expected_type": "CLEAR_UNRELATED",
    },
]


# ============================================================================
# MAIN
# ============================================================================

def main():

    separator()
    print("TEST DE FRONTERA - INSTAGRAM CLASSIFIER + IA")
    separator()

    print()
    print("Objetivo:")
    print("  Analizar casos claros y casos ambiguos/frontera.")
    print()
    print("NO se modifican reglas.")
    print("NO se modifica el classifier.")
    print("Solo observamos las respuestas reales de la IA.")
    print()

    industries = sorted(set(case["industry"] for case in CASES))

    print("Industrias probadas:")
    for industry in industries:
        print(f"  - {industry}")

    print()
    print(f"Total de casos: {len(CASES)}")

    # ------------------------------------------------------------------------
    # AI API
    # ------------------------------------------------------------------------

    print()
    separator()
    print("CONECTANDO AIAPI")
    separator()

    try:
        ai_api = AIAPI()

        print("✓ AIAPI inicializada")
        print(f"✓ API URL: {ai_api.url}")

    except Exception as e:
        print()
        print("❌ ERROR INICIALIZANDO AIAPI")
        print(type(e).__name__)
        print(str(e))
        return 1

    # ------------------------------------------------------------------------
    # CLASSIFIER
    # ------------------------------------------------------------------------

    print()
    separator()
    print("INICIALIZANDO CLASSIFIER")
    separator()

    try:
        service = InstagramProspectClassificationService(
            ai_api=ai_api
        )

        print("✓ InstagramProspectClassificationService inicializado")

    except Exception as e:
        print()
        print("❌ ERROR INICIALIZANDO CLASSIFIER")
        print(type(e).__name__)
        print(str(e))
        return 1

    # ------------------------------------------------------------------------
    # RESULTS
    # ------------------------------------------------------------------------

    results = []

    clear_competitor_ok = 0
    clear_unrelated_ok = 0
    boundary_cases = 0
    errors = 0

    # ------------------------------------------------------------------------
    # RUN CASES
    # ------------------------------------------------------------------------

    for index, case in enumerate(CASES, start=1):

        print()
        separator("-")
        print(f"TEST {index}/{len(CASES)}")
        separator("-")

        print(f"Nombre: {case['name']}")
        print(f"Industria: {case['industry']}")
        print(f"Perfil: @{case['profile']['username']}")
        print(f"Tipo de caso: {case['expected_type']}")

        campaign = make_campaign(
            case["industry"],
            case["services"],
        )

        recent_posts = [
            {
                "post_url": (
                    "https://www.instagram.com/p/BOUNDARYRECENT1/"
                ),
                "caption_text": case["post"]["caption_text"],
                "post_type": "post",
            }
        ]

        try:

            ok, result = service.classify(
                bot_personality_id=BOT_PERSONALITY_ID,
                campaign=campaign,
                profile_context=case["profile"],
                post_context=case["post"],
                recent_posts=recent_posts,
            )

        except Exception as e:

            errors += 1

            print()
            print("❌ ERROR EJECUTANDO CLASSIFY")
            print(type(e).__name__)
            print(str(e))

            results.append({
                "case": case,
                "ok": False,
                "error": str(e),
            })

            continue

        print()

        if not ok:
            errors += 1

            print("❌ classify() devolvió OK=False")

            print()
            print("RESULTADO:")
            print_json(result)

            results.append({
                "case": case,
                "ok": False,
                "result": result,
            })

            continue

        print("✓ classify() OK")

        # --------------------------------------------------------------------
        # Extract
        # --------------------------------------------------------------------

        is_competitor = result.get("is_competitor")
        relation = result.get("competitor_relation")
        vertical = result.get("business_vertical")
        confidence = result.get("classification_confidence")
        commercial_intent = result.get("commercial_intent_score")
        competitor_score = result.get("competitor_score")

        print()
        print("RESULTADO RESUMIDO")
        print(f"  is_competitor: {is_competitor}")
        print(f"  competitor_relation: {relation}")
        print(f"  business_vertical: {vertical}")
        print(f"  competitor_score: {competitor_score}")
        print(f"  commercial_intent_score: {commercial_intent}")
        print(f"  classification_confidence: {confidence}")

        evidence = result.get("classification_evidence", [])

        if isinstance(evidence, list):
            print(f"  evidence: {len(evidence)} elementos")

        # --------------------------------------------------------------------
        # Clear competitor
        # --------------------------------------------------------------------

        if case["expected_type"] == "CLEAR_COMPETITOR":

            if (
                is_competitor is True
                and relation == "DIRECT_COMPETITOR"
            ):
                clear_competitor_ok += 1
                print()
                print("✓ COMPETIDOR CLARO CORRECTAMENTE DETECTADO")
            else:
                print()
                print("❌ COMPETIDOR CLARO NO COINCIDE")

                print()
                print("RESULTADO COMPLETO:")
                print_json(result)

        # --------------------------------------------------------------------
        # Clear unrelated
        # --------------------------------------------------------------------

        elif case["expected_type"] == "CLEAR_UNRELATED":

            if (
                is_competitor is False
                and relation == "UNRELATED_BUSINESS"
            ):
                clear_unrelated_ok += 1
                print()
                print("✓ NO RELACIONADO CORRECTAMENTE DETECTADO")
            else:
                print()
                print("⚠ CASO NO RELACIONADO CON RESULTADO DIFERENTE")

                print()
                print("RESULTADO COMPLETO:")
                print_json(result)

        # --------------------------------------------------------------------
        # Boundary
        # --------------------------------------------------------------------

        elif case["expected_type"] == "BOUNDARY":

            boundary_cases += 1

            print()
            print("ℹ CASO DE FRONTERA")
            print(f"  IA decidió: {relation}")

            if relation == "ADJACENT_LOCAL_SERVICE":
                print("  → La IA lo considera ADYACENTE")

            elif relation == "UNRELATED_BUSINESS":
                print("  → La IA lo considera NO RELACIONADO")

            elif relation == "DIRECT_COMPETITOR":
                print("  → ⚠ La IA lo considera COMPETIDOR DIRECTO")

            else:
                print("  → ⚠ Relación inesperada")

        results.append({
            "case": case,
            "ok": True,
            "result": result,
        })

    # =========================================================================
    # FINAL
    # =========================================================================

    print()
    separator()
    print("RESULTADO FINAL")
    separator()

    print()
    print(f"Casos totales: {len(CASES)}")
    print(f"Competidores claros correctos: {clear_competitor_ok}")
    print(f"No relacionados claros correctos: {clear_unrelated_ok}")
    print(f"Casos de frontera analizados: {boundary_cases}")
    print(f"Errores de ejecución: {errors}")

    # ------------------------------------------------------------------------
    # RESUMEN DE FRONTERAS
    # ------------------------------------------------------------------------

    print()
    separator()
    print("RESUMEN DE CASOS DE FRONTERA")
    separator()

    for item in results:

        case = item["case"]

        if case["expected_type"] != "BOUNDARY":
            continue

        print()
        print(f"{case['name']}")
        print(f"  Industria: {case['industry']}")
        print(f"  Perfil: @{case['profile']['username']}")

        if not item.get("ok"):
            print("  Resultado: ERROR")
            continue

        result = item["result"]

        print(
            f"  competitor_relation: "
            f"{result.get('competitor_relation')}"
        )

        print(
            f"  is_competitor: "
            f"{result.get('is_competitor')}"
        )

        print(
            f"  business_vertical: "
            f"{result.get('business_vertical')}"
        )

    # ------------------------------------------------------------------------
    # CONCLUSIÓN
    # ------------------------------------------------------------------------

    print()
    separator()
    print("CONCLUSIÓN")
    separator()

    print()
    print(
        "Los casos de frontera NO se consideran PASS/FAIL "
        "por relación."
    )

    print(
        "Su objetivo es observar dónde la IA separa:"
    )

    print("  DIRECT_COMPETITOR")
    print("        ↓")
    print("  ADJACENT_LOCAL_SERVICE")
    print("        ↓")
    print("  UNRELATED_BUSINESS")

    print()
    print(
        "Esto permite decidir posteriormente si las reglas actuales "
        "de ADJACENT_LOCAL_SERVICE son suficientemente amplias."
    )

    print()
    print(
        "IMPORTANTE: este test NO realiza cambios en el classifier "
        "ni en las reglas."
    )

    separator()

    if errors:
        print()
        print("⚠ Hubo errores de ejecución.")
        return 1

    print()
    print("✓ PRUEBA DE FRONTERA COMPLETADA")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
