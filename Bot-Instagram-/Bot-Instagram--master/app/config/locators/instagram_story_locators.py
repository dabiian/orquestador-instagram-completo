class InstagramStoryLocators:
    """
    Locators centralizados para publicar historias en Instagram.

    IMPORTANTE:
    Este flujo NO navega a /stories/create/.
    Mantiene el comportamiento original de la tarea:
    - buscar input file de story
    - subir imagen
    - buscar botón final "Añadir contenido a tu historia"
    """

    # Inputs posibles para subir historia
    YOUR_STORY_FILE_INPUT = (
        "//input[@type='file' and "
        "(@accept='image/jpeg,image/png,image/heic,image/heif,video/mp4,video/quicktime' "
        "or contains(@accept, 'image') "
        "or contains(@accept, 'video'))]"
    )

    YOUR_STORY_FILE_INPUT_FALLBACK = (
        "//div[@data-pagelet='story_tray']//input[@type='file']"
    )

    FILE_INPUT_GENERIC = "//input[@type='file']"

    UPLOAD_INPUT_CANDIDATES = [
        YOUR_STORY_FILE_INPUT,
        YOUR_STORY_FILE_INPUT_FALLBACK,
        "//div[@data-pagelet='story_tray']//input[@type='file']",
        "//input[@type='file']",
    ]

    # Botón final para publicar story
    ADD_TO_YOUR_STORY_BUTTON = (
        "//button[.//span[@aria-label='Añadir contenido a tu historia' "
        "or @aria-label='Add to your story' "
        "or @aria-label='Add content to your story']]"
    )

    ADD_TO_STORY_BUTTON_CANDIDATES = [
        ADD_TO_YOUR_STORY_BUTTON,

        "//button[.//span[@aria-label='Añadir contenido a tu historia' "
        "or @aria-label='Add to your story' "
        "or @aria-label='Add content to your story']]",

        "//button[.//*[contains(normalize-space(.), 'Añadir contenido a tu historia')]]",
        "//button[.//*[contains(normalize-space(.), 'Add to your story')]]",
        "//button[.//*[contains(normalize-space(.), 'Add content to your story')]]",

        "//*[contains(normalize-space(.), 'Añadir contenido a tu historia')]",
        "//*[contains(normalize-space(.), 'Add to your story')]",
        "//*[contains(normalize-space(.), 'Add content to your story')]",

        "//*[@role='button' and contains(normalize-space(.), 'Añadir contenido a tu historia')]",
        "//*[@role='button' and contains(normalize-space(.), 'Add to your story')]",
        "//*[@role='button' and contains(normalize-space(.), 'Add content to your story')]",
    ]

    PUBLISH_ERROR_TEXTS = [
        "Something went wrong",
        "Algo salió mal",
        "Try again",
        "Inténtalo de nuevo",
        "We couldn't share your story",
        "No pudimos compartir tu historia",
        "Couldn't post",
        "No se pudo publicar",
    ]