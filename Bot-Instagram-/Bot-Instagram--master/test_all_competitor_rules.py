import json
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_CONFIG_DIR = (
    Path(__file__).resolve().parent
    / "app"
    / "utils"
    / "config"
)

INDUSTRIES = [
    "cleaning",
    "fences",
    "botanica",
    "spa",
    "spa colombia",
    "abogados",
    "marketing",
    "real_estate",
    "construction",
]

RULE_FILE = "02_competitor_filter.json"

REQUIRED_KEYS = [
    "industry",
    "core_services",
    "direct_competitor_signals",
    "possible_competitor_signals",
    "adjacent_businesses",
    "referral_opportunities",
]


# ============================================================
# HELPERS
# ============================================================

def print_separator():
    print("-" * 80)


def load_rules(industry: str):

    path = BASE_CONFIG_DIR / industry / RULE_FILE

    if not path.exists():

        return (
            False,
            path,
            None,
            f"Archivo no encontrado: {path}",
        )

    try:

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

    except json.JSONDecodeError as exc:

        return (
            False,
            path,
            None,
            f"JSON inválido: {exc}",
        )

    except Exception as exc:

        return (
            False,
            path,
            None,
            f"Error leyendo archivo: {exc}",
        )

    if not isinstance(data, dict):

        return (
            False,
            path,
            None,
            "El JSON debe contener un objeto.",
        )

    return (
        True,
        path,
        data,
        None,
    )


# ============================================================
# VALIDAR REGLAS
# ============================================================

def validate_rules(
    industry: str,
    rules: dict,
):

    errors = []

    # --------------------------------------------------------
    # INDUSTRY
    # --------------------------------------------------------

    if "industry" not in rules:

        errors.append(
            "Falta 'industry'."
        )

    else:

        json_industry = str(
            rules.get("industry") or ""
        ).strip().lower()

        expected_industry = industry.strip().lower()

        if not json_industry:

            errors.append(
                "'industry' está vacío."
            )

        elif json_industry != expected_industry:

            errors.append(
                f"'industry' es '{json_industry}' "
                f"pero se esperaba '{expected_industry}'."
            )

    # --------------------------------------------------------
    # PROPIEDADES OBLIGATORIAS
    # --------------------------------------------------------

    list_keys = [
        "core_services",
        "direct_competitor_signals",
        "possible_competitor_signals",
        "adjacent_businesses",
        "referral_opportunities",
    ]

    for key in REQUIRED_KEYS:

        if key not in rules:

            errors.append(
                f"Falta la propiedad '{key}'."
            )

    # --------------------------------------------------------
    # VALIDAR LISTAS
    # --------------------------------------------------------

    for key in list_keys:

        if key not in rules:
            continue

        values = rules[key]

        if not isinstance(values, list):

            errors.append(
                f"'{key}' debe ser una lista."
            )

            continue

        if len(values) == 0:

            errors.append(
                f"'{key}' está vacía."
            )

            continue

        for index, value in enumerate(values):

            if not isinstance(value, str):

                errors.append(
                    f"'{key}[{index}]' debe ser string."
                )

            elif not value.strip():

                errors.append(
                    f"'{key}[{index}]' está vacío."
                )

    return errors


# ============================================================
# MOSTRAR REGLAS
# ============================================================

def show_rule_summary(rules: dict):

    print()
    print("RESUMEN DE REGLAS:")

    print(
        f"  core_services: "
        f"{len(rules.get('core_services', []))}"
    )

    print(
        f"  direct_competitor_signals: "
        f"{len(rules.get('direct_competitor_signals', []))}"
    )

    print(
        f"  possible_competitor_signals: "
        f"{len(rules.get('possible_competitor_signals', []))}"
    )

    print(
        f"  adjacent_businesses: "
        f"{len(rules.get('adjacent_businesses', []))}"
    )

    print(
        f"  referral_opportunities: "
        f"{len(rules.get('referral_opportunities', []))}"
    )

    # Estas dos son opcionales en nuestra estructura,
    # por eso solo las mostramos si existen.

    if "exclude_as_competitor" in rules:

        print(
            f"  exclude_as_competitor: "
            f"{len(rules.get('exclude_as_competitor', []))}"
        )

    if "classification_priority" in rules:

        print(
            f"  classification_priority: "
            f"{len(rules.get('classification_priority', []))}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("TEST DE CARGA DE REGLAS POR INDUSTRIA")
    print("=" * 80)

    print()
    print("Directorio base:")
    print(BASE_CONFIG_DIR)
    print()

    total = len(INDUSTRIES)

    passed = 0
    failed = 0

    results = []

    for industry in INDUSTRIES:

        print_separator()
        print(f"INDUSTRIA: {industry}")
        print_separator()

        ok, path, rules, error = load_rules(
            industry
        )

        # ----------------------------------------------------
        # ERROR DE ARCHIVO
        # ----------------------------------------------------

        if not ok:

            print("❌ FAIL")
            print(f"   {error}")

            failed += 1

            results.append({
                "industry": industry,
                "ok": False,
                "reason": error,
            })

            continue

        print("✓ Archivo encontrado")
        print(f"  {path}")

        # ----------------------------------------------------
        # VALIDACIÓN
        # ----------------------------------------------------

        errors = validate_rules(
            industry=industry,
            rules=rules,
        )

        if errors:

            print()
            print("❌ FAIL - errores:")

            for error in errors:

                print(
                    f"   - {error}"
                )

            failed += 1

            results.append({
                "industry": industry,
                "ok": False,
                "reason": errors,
            })

            continue

        # ----------------------------------------------------
        # OK
        # ----------------------------------------------------

        print("✓ JSON válido")
        print("✓ Industry correcta")
        print("✓ Estructura válida")

        show_rule_summary(
            rules
        )

        print()
        print("✓ PASS")

        passed += 1

        results.append({
            "industry": industry,
            "ok": True,
        })

    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    print()
    print("=" * 80)
    print("RESULTADO FINAL")
    print("=" * 80)

    print()
    print(f"Total industrias: {total}")
    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")

    print()

    for result in results:

        if result["ok"]:

            print(
                f"✓ {result['industry']}: PASS"
            )

        else:

            print(
                f"❌ {result['industry']}: FAIL"
            )

    print()

    if failed == 0:

        print("=" * 80)
        print("TODAS LAS REGLAS ESTÁN CORRECTAS")
        print("=" * 80)

        return 0

    print("=" * 80)
    print("HAY REGLAS QUE NECESITAN CORRECCIÓN")
    print("=" * 80)

    return 1


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    raise SystemExit(
        main()
    )
