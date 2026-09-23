class InstagramNotificationsLocators:
    NOTIFICATIONS_BUTTON = (
        "//a[@role='link' and .//*[name()='svg' and "
        "(@aria-label='Notificaciones' or @aria-label='Notifications')]]"
    )

    NOTIFICATIONS_PANEL_ROOT = (
        "//*[.//*[@role='heading']//*[normalize-space()='Notificaciones' "
        "or normalize-space()='Notifications']]"
    )

    ALL_TAB = (
        "//*[@role='button' and .//span[normalize-space()='Todas' "
        "or normalize-space()='All']]"
    )

    COMMENTS_TAB = (
        "//*[@role='button' and .//span[normalize-space()='Comentarios' "
        "or normalize-space()='Comments']]"
    )

    CLOSE_BUTTON = (
        "//*[@role='button' and (@aria-label='Cerrar' or @aria-label='Close')]"
    )