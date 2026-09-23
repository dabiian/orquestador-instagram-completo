class InstagramCommonLocators:
    REST_MODE_MODAL = (
        "//div[@role='dialog' and .//h3[normalize-space()='Estás en modo descanso']]"
    )

    REST_MODE_ACCEPT_BUTTON = (
        "//div[@role='dialog' and .//h3[normalize-space()='Estás en modo descanso']]"
        "//*[@role='button' and normalize-space()='Aceptar']"
    )

    FOLLOWING_XPATHS = [
        "//button[.//div[normalize-space()='Siguiendo']]",
        "//button[.//div[normalize-space()='Following']]",
        "//button[.//div[normalize-space()='Solicitado']]",
        "//button[.//div[normalize-space()='Requested']]",
        "//*[@role='button' and .//div[normalize-space()='Siguiendo']]",
        "//*[@role='button' and .//div[normalize-space()='Following']]",
        "//*[@role='button' and .//div[normalize-space()='Solicitado']]",
        "//*[@role='button' and .//div[normalize-space()='Requested']]",
    ]

    FOLLOW_XPATHS = [
        "//button[.//div[normalize-space()='Seguir']]",
        "//button[.//div[normalize-space()='Follow']]",
        "//*[@role='button' and .//div[normalize-space()='Seguir']]",
        "//*[@role='button' and .//div[normalize-space()='Follow']]",
    ]

    DATE_XPATHS = [
        (
            "(//article//a["
            "(contains(@href,'/p/') or contains(@href,'/reel/') or contains(@href,'/tv/')) "
            "and not(contains(@href,'/c/'))"
            "]//time[@datetime])[last()]"
        ),
        "(//article//time[@datetime])[1]",
        "//time[@datetime]",
    ]

    LIKE_BUTTON_XPATHS = [
        "//article//*[name()='svg' and @aria-label='Me gusta']/ancestor::*[@role='button'][1]",
        "//article//*[name()='svg' and @aria-label='Like']/ancestor::*[@role='button'][1]",
        "//span//*[name()='svg' and @aria-label='Me gusta']/ancestor::*[@role='button'][1]",
        "//span//*[name()='svg' and @aria-label='Like']/ancestor::*[@role='button'][1]",
    ]

    PROFILE_TAGGED_TAB = (
        "//div[@role='tablist']//a[contains(@href,'/tagged/')]"
    )

    PROFILE_TAGGED_TAB_SELECTED = (
        "//div[@role='tablist']//a[contains(@href,'/tagged/') and @aria-selected='true']"
    )

    PROFILE_TAGGED_POST_LINKS = (
        "//a[@role='link' "
        "and (contains(@href,'/p/') or contains(@href,'/reel/') or contains(@href,'/tv/')) "
        "and .//img]"
    )