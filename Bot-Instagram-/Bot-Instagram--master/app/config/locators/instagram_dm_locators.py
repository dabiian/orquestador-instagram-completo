class InstagramDMLocators:
    """
    Locators/scripts centralizados para Instagram Direct Messages.

    Usado por:
    - InteractWithInstagramUnreadMessagesTask

    Aquí van:
    - navegación al inbox
    - lista de chats
    - chats no leídos
    - raíz del chat abierto
    - lectura de mensajes visibles
    - input composer
    - botón enviar
    """

    # =========================================================
    # INBOX NAVIGATION
    # =========================================================

    MESSAGES_NAV = "//a[contains(@href, '/direct/inbox') and @role='link']"

    INBOX_LIST = "//*[@data-pagelet='IGDInboxThreadListScrollableAreaPagelet']"

    UNREAD_CHAT_ITEMS = (
        "//*[@data-pagelet='IGDInboxThreadListScrollableAreaPagelet']"
        "//*[@role='button' and "
        "(.//div[normalize-space()='Unread'] "
        "or .//div[normalize-space()='No leído'] "
        "or .//div[normalize-space()='Sin leer']) "
        "and .//span[@title]]"
    )

    CHAT_TITLE_REL = ".//span[@title][1]"

    # =========================================================
    # OPEN CHAT
    # =========================================================

    DM_CHAT_ROOT = "//*[@data-pagelet='IGDMessagesList']"

    DM_CONTACT_NAME = "//*[@data-pagelet='IGDMessagesList']//h2//span[@title][1]"

    DM_MESSAGE_GROUPS = "//*[@data-pagelet='IGDMessagesList']//*[@role='group']"

    DM_COMPOSER_INPUT = (
        "//*[@role='textbox' and @contenteditable='true' "
        "and (@aria-placeholder='Envía un mensaje...' "
        "or @aria-placeholder='Send a message...')]"
    )

    DM_SEND_BUTTON = (
        "//*[@role='button' and (@aria-label='Enviar' or @aria-label='Send')]"
    )

    # =========================================================
    # SMALL JS HELPERS
    # =========================================================

    SCROLL_INTO_VIEW_CENTER_SCRIPT = (
        "arguments[0].scrollIntoView({block:'center', inline:'center'});"
    )

    CLICK_ELEMENT_SCRIPT = "arguments[0].click();"

    READ_DM_INPUT_TEXT_SCRIPT = """
    return (arguments[0].innerText || arguments[0].textContent || '').trim();
    """

    # =========================================================
    # READ VISIBLE DM MESSAGES
    # =========================================================

    GET_VISIBLE_CHAT_MESSAGES_SCRIPT = r"""
    return (() => {
        const norm = (txt) => (txt || '').replace(/\s+/g, ' ').trim();

        const result = {
            contact_name: "",
            messages: []
        };

        const nameEl =
            document.querySelector('[data-pagelet="IGDMessagesList"] h2 span[title]') ||
            document.querySelector('h2 span[title]');

        if (nameEl) {
            result.contact_name = norm(nameEl.textContent);
        }

        const groups = [
            ...document.querySelectorAll('[data-pagelet="IGDMessagesList"] [role="group"]')
        ];

        for (const group of groups) {
            try {
                const wrapper = group.closest('.x13dflua') || group.parentElement;
                const possibleTime = wrapper?.querySelector('span[dir="auto"]');
                const timeText = norm(possibleTime?.textContent || "");

                const otherProfileAnchor =
                    group.querySelector('a[href^="/"][aria-label*="Open the profile page"]') ||
                    group.querySelector('a[href^="/"][href]:not([href*="/direct/"])');

                const otherProfileHref = otherProfileAnchor
                    ? new URL(otherProfileAnchor.getAttribute("href"), location.origin).href
                    : "";

                const sender = otherProfileAnchor ? "other" : "me";

                const textDivs = [
                    ...group.querySelectorAll('div[dir="auto"]')
                ];

                for (const div of textDivs) {
                    const text = norm(div.textContent || "");
                    if (!text) continue;

                    result.messages.push({
                        sender,
                        text,
                        time: timeText,
                        profile_href: otherProfileHref,
                        contact_name: result.contact_name
                    });
                }
            } catch (e) {}
        }

        return result;
    })();
    """