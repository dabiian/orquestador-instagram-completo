class InstagramPostLocators:
    """
    Locators centralizados para crear/publicar posts en Instagram.
    """

    HOME_URL = "https://www.instagram.com/"

    # Icono lateral de crear nueva publicación
    NEW_POST_ICON_CSS = (
        'svg[aria-label="Nueva publicación"], '
        'svg[aria-label="New post"], '
        'svg[aria-label="Crear"], '
        'svg[aria-label="Create"]'
    )

    # Composer real listo
    POST_COMPOSER_READY = (
        "//*[contains(normalize-space(.), 'Arrastra las fotos y los vídeos aquí')]"
        " | //*[contains(normalize-space(.), 'Drag photos and videos here')]"
        " | //button[normalize-space(.)='Seleccionar del ordenador']"
        " | //button[normalize-space(.)='Select from computer']"
        " | //input[@type='file']"
    )

    FILE_INPUT = "//input[@type='file']"

    SELECT_FROM_COMPUTER_BUTTON = (
        "//button[normalize-space(.)='Seleccionar del ordenador']"
        " | //button[normalize-space(.)='Select from computer']"
    )

    NEXT_BUTTON = (
        "//button[normalize-space(.)='Siguiente']"
        " | //button[normalize-space(.)='Next']"
        " | //*[@role='button' and normalize-space(.)='Siguiente']"
        " | //*[@role='button' and normalize-space(.)='Next']"
        " | //*[@tabindex='0' and normalize-space(.)='Siguiente']"
        " | //*[@tabindex='0' and normalize-space(.)='Next']"
    )

    CAPTION_INPUT = (
        "//div[@aria-label='Write a caption...']"
        " | //div[@aria-label='Escribe un pie de foto...']"
        " | //textarea[@aria-label='Write a caption...']"
        " | //textarea[@aria-label='Escribe un pie de foto...']"
        " | //div[@contenteditable='true' and @role='textbox']"
        " | //div[@contenteditable='true']"
    )

    SHARE_BUTTON_ALL = (
        "//*[@role='button' and normalize-space(.)='Compartir']"
        " | //*[@role='button' and normalize-space(.)='Share']"
        " | //*[@role='button' and normalize-space(.)='Publicar']"
        " | //*[@role='button' and normalize-space(.)='Post']"
        " | //button[normalize-space(.)='Compartir']"
        " | //button[normalize-space(.)='Share']"
        " | //button[normalize-space(.)='Publicar']"
        " | //button[normalize-space(.)='Post']"
    )

    CREATE_MENU_POST_OPTIONS = [
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Publicación'] and .//svg[@aria-label='Publicación']]",
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Publicación']]",
        "//span[normalize-space()='Publicación']/ancestor::a[@role='link'][1]",
        "//svg[@aria-label='Publicación']/ancestor::a[@role='link'][1]",

        "//a[@role='link' and @href='#' and .//span[normalize-space()='Post'] and .//svg[@aria-label='Post']]",
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Post']]",
        "//span[normalize-space()='Post']/ancestor::a[@role='link'][1]",
        "//svg[@aria-label='Post']/ancestor::a[@role='link'][1]",
    ]

    CREATE_MENU_DETECTORS = [
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Publicación']]",
        "//a[@role='link' and .//span[normalize-space()='Publicación']]",
        "//span[normalize-space()='Publicación']/ancestor::a[@role='link'][1]",
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Post']]",
        "//a[@role='link' and .//span[normalize-space()='Post']]",
        "//span[normalize-space()='Post']/ancestor::a[@role='link'][1]",
        "//a[@role='link' and .//span[normalize-space()='IA']]",
        "//a[@role='link' and .//span[normalize-space()='AI']]",
    ]

    NEW_POST_CLICKABLE_ANCESTORS = [
        "./ancestor::div[@aria-selected][1]",
        "./ancestor::*[@role='button'][1]",
        "./ancestor::button[1]",
        "./ancestor::a[1]",
        "./ancestor::div[1]",
        "./ancestor::div[2]",
        "./ancestor::div[3]",
    ]

    PUBLISH_ERROR_TEXTS = [
        "Something went wrong",
        "Algo salió mal",
        "Try again",
        "Inténtalo de nuevo",
        "We couldn't share your post",
        "No pudimos compartir tu publicación",
        "Couldn't post",
        "No se pudo publicar",
    ]