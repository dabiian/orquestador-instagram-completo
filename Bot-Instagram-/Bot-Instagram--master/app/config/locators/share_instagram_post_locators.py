class ShareInstagramPostLocators:
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

    POST_COMPOSER_READY = (
        "//*[contains(normalize-space(.), 'Arrastra las fotos y los vídeos aquí')]"
        " | "
        "//*[contains(normalize-space(.), 'Drag photos and videos here')]"
        " | "
        "//button[normalize-space(.)='Seleccionar del ordenador']"
        " | "
        "//button[normalize-space(.)='Select from computer']"
        " | "
        "//input[@type='file']"
    )

    CREATE_POST_ICON_CSS = 'svg[aria-label="Nueva publicación"], svg[aria-label="New post"]'

    SELECT_FROM_COMPUTER_BUTTON = (
        "//button[normalize-space(.)='Seleccionar del ordenador']"
        " | "
        "//button[normalize-space(.)='Select from computer']"
    )

    FILE_INPUT = "//input[@type='file']"

    NEXT_BUTTON = (
        "//button[normalize-space(.)='Siguiente']"
        " | "
        "//button[normalize-space(.)='Next']"
        " | "
        "//*[@role='button' and normalize-space(.)='Siguiente']"
        " | "
        "//*[@role='button' and normalize-space(.)='Next']"
        " | "
        "//*[@tabindex='0' and normalize-space(.)='Siguiente']"
        " | "
        "//*[@tabindex='0' and normalize-space(.)='Next']"
    )

    CAPTION_INPUT = (
        "//*[@role='textbox' and @contenteditable='true' and ("
        "@aria-label='Escribe un pie de foto o vídeo…' "
        "or @aria-label='Write a caption…' "
        "or @aria-placeholder='Escribe un pie de foto o vídeo…' "
        "or @aria-placeholder='Write a caption…'"
        ")]"
        " | "
        "//*[@role='textbox' and @contenteditable='true']"
    )

    SHARE_BUTTON = (
        "(//*[@role='button' and @tabindex='0' and normalize-space(.)='Compartir']"
        " | "
        "//*[@role='button' and @tabindex='0' and normalize-space(.)='Share']"
        " | "
        "//*[@role='button' and @tabindex='0' and normalize-space(.)='Publicar']"
        " | "
        "//*[@role='button' and @tabindex='0' and normalize-space(.)='Post'])[last()]"
    )

    SHARE_BUTTON_ALL = (
        "//*[@role='button' and @tabindex='0' and ("
        "normalize-space(.)='Compartir' or "
        "normalize-space(.)='Share' or "
        "normalize-space(.)='Publicar' or "
        "normalize-space(.)='Post'"
        ")]"
    )


    TAG_TOOLTIP = (
        "//*[contains(normalize-space(.), 'Haz clic en la foto para etiquetar a personas')]"
        " | "
        "//*[contains(normalize-space(.), 'Click on the photo to tag people')]"
    )

    TAG_SEARCH_RESULTS_CONTAINER = (
        "//input[@name='userSearchInput']/ancestor::div[contains(@class,'html-div')][1]"
        "/following::div[.//div[contains(@class,'_acmu')]][1]"
        " | "
        "//div[.//div[contains(@class,'_acmu')]]"
    )


    TAG_PEOPLE_BUTTON = (
        "//button[normalize-space(.)='Etiquetar personas']"
        " | "
        "//button[normalize-space(.)='Tag people']"
        " | "
        "//*[@role='button' and .//span[normalize-space(.)='Etiquetar personas']]"
        " | "
        "//*[@role='button' and .//span[normalize-space(.)='Tag people']]"
        " | "
        "//*[@role='button' and .//div[normalize-space(.)='Etiquetar personas']]"
        " | "
        "//*[@role='button' and .//div[normalize-space(.)='Tag people']]"
        " | "
        "//*[self::span or self::div][normalize-space(.)='Etiquetar personas']/ancestor::button[1]"
        " | "
        "//*[self::span or self::div][normalize-space(.)='Tag people']/ancestor::button[1]"
        " | "
        "//*[self::span or self::div][normalize-space(.)='Etiquetar personas']/ancestor::*[@role='button'][1]"
        " | "
        "//*[self::span or self::div][normalize-space(.)='Tag people']/ancestor::*[@role='button'][1]"
        " | "
        "//*[self::span or self::div][normalize-space(.)='Etiquetar personas']/ancestor::div[@tabindex='0'][1]"
        " | "
        "//*[self::span or self::div][normalize-space(.)='Tag people']/ancestor::div[@tabindex='0'][1]"
    )

    TAG_PEOPLE_MODAL_TITLE = (
        "//div[normalize-space(.)='Etiquetar personas']"
        " | "
        "//div[normalize-space(.)='Tag people']"
    )

    TAG_PEOPLE_DONE_BUTTON = (
        "//button[normalize-space(.)='Listo']"
        " | "
        "//button[normalize-space(.)='Done']"
    )

    TAG_HINT_CLICKABLE = (
        "//*[@role='button' and .//*[contains(normalize-space(.), 'Haz clic en la foto para etiquetar a personas')]]"
        " | "
        "//*[@role='button' and .//*[contains(normalize-space(.), 'Toca la foto para etiquetar personas.')]]"
        " | "
        "//*[@role='button' and .//*[contains(normalize-space(.), 'Click on the photo to tag people')]]"
        " | "
        "//*[@role='button' and .//*[contains(normalize-space(.), 'Tap the photo to tag people')]]"
        " | "
        "//*[contains(normalize-space(.), 'Haz clic en la foto para etiquetar a personas')]/ancestor::*[@role='button'][1]"
        " | "
        "//*[contains(normalize-space(.), 'Toca la foto para etiquetar personas.')]/ancestor::*[@role='button'][1]"
        " | "
        "//*[contains(normalize-space(.), 'Click on the photo to tag people')]/ancestor::*[@role='button'][1]"
        " | "
        "//*[contains(normalize-space(.), 'Tap the photo to tag people')]/ancestor::*[@role='button'][1]"
    )

    TAG_PEOPLE_PREVIEW_IMAGE = (
        "//img[@alt='Foto para la ubicación de etiquetas']"
        " | "
        "//img[@alt='Photo for tag location']"
    )

    USER_SEARCH_INPUT = (
        "//input[@name='userSearchInput']"
        " | "
        "//input[@placeholder='Busca']"
        " | "
        "//input[@placeholder='Search']"
    )

    TAG_SEARCH_RESULT_BY_USERNAME_TEMPLATE = (
        "//div[contains(@class,'_acmu') and normalize-space(.)='{username}']/ancestor::button[1]"
        " | "
        "//div[normalize-space(.)='{username}']/ancestor::button[1]"
    )

    TAG_PEOPLE_CLICK_SURFACE = (
        "//img[@alt='Foto para la ubicación de etiquetas']/following-sibling::div[@role='button' and @tabindex='0'][1]"
        " | "
        "//img[@alt='Photo for tag location']/following-sibling::div[@role='button' and @tabindex='0'][1]"
    )


    # =========================================================
    # CREATE / POST COMPOSER
    # =========================================================

    NEW_POST_ICON_CSS = (
        'svg[aria-label="Nueva publicación"], '
        'svg[aria-label="New post"]'
    )

    NEW_POST_CLICKABLE_ANCESTOR_XPATHS = [
        "./ancestor::div[@aria-selected][1]",
        "./ancestor::*[@role='button'][1]",
        "./ancestor::button[1]",
        "./ancestor::a[1]",
        "./ancestor::div[1]",
        "./ancestor::div[2]",
        "./ancestor::div[3]",
    ]

    CREATE_MENU_OPENED_XPATHS = [
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Publicación']]",
        "//a[@role='link' and .//span[normalize-space()='Publicación']]",
        "//span[normalize-space()='Publicación']/ancestor::a[@role='link'][1]",
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Post']]",
        "//a[@role='link' and .//span[normalize-space()='Post']]",
        "//span[normalize-space()='Post']/ancestor::a[@role='link'][1]",
        "//a[@role='link' and .//span[normalize-space()='IA']]",
        "//a[@role='link' and .//span[normalize-space()='AI']]",
    ]

    POST_OPTION_XPATHS = [
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Publicación'] and .//svg[@aria-label='Publicación']]",
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Publicación']]",
        "//span[normalize-space()='Publicación']/ancestor::a[@role='link'][1]",
        "//svg[@aria-label='Publicación']/ancestor::a[@role='link'][1]",
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Post'] and .//svg[@aria-label='Post']]",
        "//a[@role='link' and @href='#' and .//span[normalize-space()='Post']]",
        "//span[normalize-space()='Post']/ancestor::a[@role='link'][1]",
        "//svg[@aria-label='Post']/ancestor::a[@role='link'][1]",
    ]

    POST_COMPOSER_READY_XPATHS = [
        POST_COMPOSER_READY,
        "//button[normalize-space()='Seleccionar del ordenador']",
        "//button[normalize-space()='Select from computer']",
        "//input[@type='file']",
        "//div[@role='button'][normalize-space()='Siguiente']",
        "//div[@role='button'][normalize-space()='Next']",
        "//button[normalize-space()='Siguiente']",
        "//button[normalize-space()='Next']",
    ]

    # =========================================================
    # ACTIVE UPLOAD DIALOG
    # =========================================================

    ACTIVE_DIALOG_EXPECTED_UPLOAD_UI_REL_XPATH = (
        ".//button[normalize-space()='Seleccionar del ordenador' "
        "or normalize-space()='Select from computer' "
        "or normalize-space()='Siguiente' "
        "or normalize-space()='Next']"
    )

    ACTIVE_DIALOG_FILE_INPUTS_REL_XPATH = (
        ".//input[@type='file' and not(@disabled)]"
    )

    ACTIVE_DIALOG_NEXT_BUTTONS_REL_XPATH = (
        ".//div[@role='button'][normalize-space()='Siguiente' or normalize-space()='Next']"
    )

    MAKE_FILE_INPUT_VISIBLE_SCRIPT = """
    arguments[0].style.display = 'block';
    arguments[0].style.visibility = 'visible';
    arguments[0].style.opacity = '1';
    arguments[0].removeAttribute('hidden');
    arguments[0].removeAttribute('aria-hidden');
    """

    CLICK_ELEMENT_SCRIPT = """
    arguments[0].scrollIntoView({
        block: 'center',
        inline: 'center'
    });

    const el = arguments[0];

    const rect = el.getBoundingClientRect();
    const x = Math.floor(rect.left + rect.width / 2);
    const y = Math.floor(rect.top + rect.height / 2);

    ['mouseover', 'mouseenter', 'mousedown', 'mouseup', 'click'].forEach(type => {
        try {
            el.dispatchEvent(new MouseEvent(type, {
                bubbles: true,
                cancelable: true,
                view: window,
                clientX: x,
                clientY: y
            }));
        } catch (e) {}
    });

    if (typeof el.click === 'function') {
        el.click();
    }
    """

    CLICK_TAG_SURFACE_SCRIPT = """
    const surface = arguments[0];
    const relX = arguments[1];
    const relY = arguments[2];

    const rect = surface.getBoundingClientRect();
    const clientX = rect.left + (rect.width * relX);
    const clientY = rect.top + (rect.height * relY);

    ['mousemove', 'mousedown', 'mouseup', 'click'].forEach(type => {
        surface.dispatchEvent(new MouseEvent(type, {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX,
            clientY
        }));
    });
    """