class ShareInstagramStoryLocators:
    SAVE_LOGIN_INFO_POPUP_TITLE = (
        "//*[self::span or self::div]["
        "contains(normalize-space(.), '¿Guardar tu información de inicio de sesión?') "
        "or contains(normalize-space(.), 'Save your login info?')"
        "]"
    )

    SAVE_LOGIN_INFO_NOT_NOW = (
        "//*[self::button or @role='button'][normalize-space(.)='Ahora no']"
        " | "
        "//*[self::button or @role='button'][normalize-space(.)='Not now']"
        " | "
        "//*[self::button or @role='button'][normalize-space(.)='Not Now']"
    )

    YOUR_STORY_FILE_INPUT = (
        "//div[@data-pagelet='story_tray']"
        "//span[contains(normalize-space(.), 'Tu historia') or contains(normalize-space(.), 'Your story')]"
        "/ancestor::*[@role='button'][1]"
        "//input[@type='file']"
    )

    YOUR_STORY_FILE_INPUT_FALLBACK = (
        "//div[@data-pagelet='story_tray']//input[@type='file']"
    )

    ADD_TO_YOUR_STORY_BUTTON = (
        "//*[self::button or @role='button']["
        "contains(normalize-space(.), 'Añadir contenido a tu historia') "
        "or contains(normalize-space(.), 'Add to your story') "
        "or contains(normalize-space(.), 'Add content to your story') "
        "or @aria-label='Añadir contenido a tu historia' "
        "or @aria-label='Add to your story' "
        "or @aria-label='Add content to your story'"
        "]"
    )

    ROTATE_DEVICE_OVERLAY = (
        "//*[contains(normalize-space(.), 'Gira el dispositivo para añadirlo a tu historia.') "
        "or contains(normalize-space(.), 'Rotate your device to add it to your story.')]"
    )

    ROTATE_DEVICE_ALERT = (
        "//*[@role='alert' and ("
        "contains(normalize-space(.), 'Gira el dispositivo para añadirlo a tu historia.') "
        "or contains(normalize-space(.), 'Rotate your device to add it to your story.')"
        ")]"
    )