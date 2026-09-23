import time

from app.core.browser import Automate
from selenium.webdriver.common.by import By


def main():
    print("=" * 70)
    print("TEST SELF-HEALER - PRUEBA 3: MULTIPLES LOCATORS GUARDADOS")
    print("=" * 70)

    bot = Automate(self_healer_enabled=True)

    try:
        print("\n[1] Abriendo navegador...")
        bot.open_browser("https://www.instagram.com/")

        driver = bot.driver

        print(f"[2] Tipo de driver: {type(driver).__name__}")

        print("\n[3] Abriendo Instagram...")
        driver.get("https://www.instagram.com/")

        time.sleep(5)

        print(f"[4] URL actual: {driver.current_url}")

        # ----------------------------------------------------------
        # IMPORTANTE
        #
        # Usamos EXACTAMENTE la misma identidad que usa el driver.
        # No agregamos description diferente.
        # ----------------------------------------------------------

        fake_xpath = "//a[@id='SELF_HEALER_TEST_FAKE_LOCATOR']"

        print("\n[5] Locator original:")
        print(f"    {fake_xpath}")

        identity_method = getattr(driver, "_identity", None)

        if identity_method is None:
            print("[ERROR] El driver no expone _identity()")
            return

        identity = identity_method(
            None,
            None,
            By.XPATH,
            fake_xpath,
            description="",
        )

        print("\n[6] Identidad calculada:")
        print(f"    project_name = {identity.project_name}")
        print(f"    framework    = {identity.framework}")
        print(f"    page_key     = {identity.page_key}")
        print(f"    element_key  = {identity.element_key}")

        # ----------------------------------------------------------
        # Mostrar TODOS los locators de esa identidad
        # ----------------------------------------------------------

        store = getattr(driver, "store", None)

        if store is None:
            print("[ERROR] El driver no expone .store")
            return

        print("\n[7] Locators encontrados en SQLite:")

        locators = store.list_locators(identity)

        if not locators:
            print("    No hay locators para esta identidad.")

        else:
            for index, locator in enumerate(
                locators,
                start=1,
            ):
                print(
                    f"    #{index} | "
                    f"enabled={locator.get('enabled')} | "
                    f"successes={locator.get('successes')} | "
                    f"failures={locator.get('failures')} | "
                    f"confidence={locator.get('confidence')} | "
                    f"{locator.get('strategy')}="
                    f"{locator.get('value')}"
                )

        # ----------------------------------------------------------
        # Ahora probamos la resolución real
        # ----------------------------------------------------------

        print("\n[8] Ejecutando locator falso...")

        try:
            element = driver.find_element(
                By.XPATH,
                fake_xpath,
            )

            print("\n=== SELF-HEALER RECUPERÓ EL ELEMENTO ===")
            print(f"Elemento: {element}")

        except Exception as exc:
            print(
                "\n=== SELF-HEALER NO RECUPERÓ EL ELEMENTO ==="
            )
            print(f"Excepción: {type(exc).__name__}")
            print(f"Detalle: {exc}")

        # ----------------------------------------------------------
        # Mostrar nuevamente la BD
        # ----------------------------------------------------------

        print("\n[9] Locators después de la resolución:")

        locators = store.list_locators(identity)

        if not locators:
            print("    No hay locators almacenados.")

        else:
            for index, locator in enumerate(
                locators,
                start=1,
            ):
                print(
                    f"    #{index} | "
                    f"enabled={locator.get('enabled')} | "
                    f"successes={locator.get('successes')} | "
                    f"failures={locator.get('failures')} | "
                    f"confidence={locator.get('confidence')} | "
                    f"{locator.get('strategy')}="
                    f"{locator.get('value')}"
                )

        print("\n[10] Esperando 5 segundos...")
        time.sleep(5)

    except Exception as exc:
        print("\n=== ERROR GENERAL ===")
        print(f"{type(exc).__name__}: {exc}")

    finally:
        print("\n[11] Cerrando navegador...")

        try:
            bot.close_browser()
        except Exception as exc:
            print(
                f"[WARN] Error cerrando navegador: {exc}"
            )

        print("\nTEST TERMINADO.")


if __name__ == "__main__":
    main()