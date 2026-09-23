class InstagramPostContextLocators:
    POST_ARTICLE = "//article"

    POST_AUTHOR_USERNAME_1 = (
        "//article//header//a[starts-with(@href,'/') and normalize-space()!=''][1]"
    )

    POST_AUTHOR_USERNAME = (
        ".//div[contains(@class,'_a9zr')]//h2//a[contains(@href,'/') and normalize-space()]"
    )

    POST_AUTHOR_PROFILE_HREF = (
        "//article//header//a[starts-with(@href,'/') and normalize-space()!=''][1]"
    )

    POST_CAPTION = (
        "//article//h1[normalize-space()]"
    )

    POST_CAPTION_1 = (
        ".//div[contains(@class,'_a9zr')]//h1[@dir='auto' and normalize-space()]"
    )

    POST_CAPTION_FALLBACK = (
        "//article//*[self::h1 or self::span][normalize-space()]"
    )

    POST_CAPTION_FALLBACK_1 = (
        ".//div[contains(@class,'_a9zr')]//*[self::h1 or self::span][normalize-space()]"
    )

    POST_CAPTION_NEW = "//div[contains(@class,'_a9zr')]//h1[@dir='auto' and normalize-space()]"

    REPOST_BUTTON = (
        "//*[self::div or self::button][@role='button' and .//svg[@aria-label='Republicar' or @aria-label='Repost']]"
    )

    REPOST_SVG = (
        "//svg[@aria-label='Republicar' or @aria-label='Repost']"
    )