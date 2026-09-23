class InteractWithInstagramFollowersLocators:
    HOME_PAGE = "https://www.instagram.com/"

    MY_PROFILE_LINK = (
        "(//a[@role='link' and starts-with(@href, '/') "
        "and .//img[contains(@alt,'Foto del perfil') or contains(@alt,'profile picture')]])[1]"
    )

    # =========================================================
    # FOLLOWERS MODAL
    # =========================================================

    # Legacy. Lo dejamos por compatibilidad.
    FOLLOWERS_BUTTON = "//a[@role='link' and contains(@href,'/followers/')]"

    # Locators robustos para abrir el modal de seguidores.
    FOLLOWERS_BUTTON_XPATHS = [
        "//header//a[contains(@href,'/followers/')]",

        (
            "//header//*[self::a or self::button or @role='button' or self::div or self::span]"
            "[contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', "
            "'abcdefghijklmnopqrstuvwxyzáéíóú'), 'seguidores') "
            "and not(contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', "
            "'abcdefghijklmnopqrstuvwxyzáéíóú'), 'seguidos'))]"
        ),

        (
            "//header//*[self::a or self::button or @role='button' or self::div or self::span]"
            "[contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'followers') "
            "and not(contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'following'))]"
        ),
    ]

    FOLLOWERS_MODAL = "//div[@role='dialog']"

    FOLLOWERS_SUGGESTIONS_HEADER = (
        "//div[@role='dialog']//h4["
        "normalize-space()='Sugerencias para ti' "
        "or normalize-space()='Suggestions for you'"
        "]"
    )

    FOLLOWERS_USERS_BEFORE_SUGGESTIONS = (
        "//div[@role='dialog']"
        "//h4[normalize-space()='Sugerencias para ti' or normalize-space()='Suggestions for you']"
        "/preceding::a[@role='link' and contains(@class,'notranslate') and starts-with(@href,'/') "
        "and not(contains(@href,'/followers/')) "
        "and not(contains(@href,'/following/')) "
        "and not(contains(@href,'/explore/')) "
        "and not(contains(@href,'/reels/')) "
        "and not(contains(@href,'/reel/')) "
        "and not(contains(@href,'/p/')) "
        "and not(contains(@href,'/stories/')) "
        "and not(contains(@href,'/accounts/'))]"
    )

    FOLLOWERS_USERS = (
        "//div[@role='dialog']//a[@role='link' "
        "and contains(@class,'notranslate') "
        "and starts-with(@href,'/') "
        "and not(contains(@href,'/followers/')) "
        "and not(contains(@href,'/following/')) "
        "and not(contains(@href,'/explore/')) "
        "and not(contains(@href,'/reels/')) "
        "and not(contains(@href,'/reel/')) "
        "and not(contains(@href,'/p/')) "
        "and not(contains(@href,'/stories/')) "
        "and not(contains(@href,'/accounts/'))]"
    )

    # =========================================================
    # PROFILE POSTS
    # =========================================================

    PROFILE_POST_LINKS = (
        "//main//a[contains(@href,'/p/') and not(ancestor::div[@role='dialog'])]"
    )

    PROFILE_POST_LINKS_VIDEOS = (
        "//main//a["
        "(contains(@href,'/p/') or contains(@href,'/reel/') or contains(@href,'/tv/')) "
        "and not(ancestor::div[@role='dialog'])"
        "]"
    )

    # =========================================================
    # POST COMMENTS / LIKE LEGACY
    # =========================================================

    POST_MAIN_COMMENTS = (
        "//ul[contains(@class,'_a9ym')]/div[@role='button']/li[contains(@class,'_a9zj')]"
    )

    POST_COMMENT_USERNAME_REL = ".//h3//a[@role='link' and starts-with(@href,'/')]"

    POST_COMMENT_TEXT_REL = ".//h3/following-sibling::div[1]//span[@dir='auto']"

    POST_COMMENT_TIME_REL = ".//a[contains(@href,'/c/')]/time"

    POST_LOAD_MORE_COMMENTS = (
        "//button[.//title[normalize-space()='Cargar más comentarios' "
        "or normalize-space()='Load more comments']]"
    )

    POST_COMMENT_BOX = (
        "//form//textarea["
        "@aria-label='Añade un comentario...' "
        "or @placeholder='Añade un comentario...' "
        "or @aria-label='Add a comment…' "
        "or @aria-label='Add a comment...'"
        "]"
    )

    POST_NO_COMMENTS_STATE = (
        "//h2[normalize-space()='Todavía no hay comentarios.' "
        "or normalize-space()='No comments yet.']"
    )

    POST_COMMENT_PUBLISH_ENABLED = (
        "//form//div[@role='button' and "
        "(normalize-space()='Publicar' or normalize-space()='Post')]"
    )

    POST_COMMENT_PUBLISH = (
        "//form//div[@role='button']["
        ".//span[normalize-space()='Publicar' or normalize-space()='Post']"
        "]"
    )

    POST_LIKE_BUTTON_NOT_LIKED = (
        "(//section[.//svg[@aria-label='Comentar' or @aria-label='Comment']]"
        "//span[contains(@class,'x1qfufaz')]"
        "//div[@role='button'][.//svg[@aria-label='Me gusta' or @aria-label='Like']])[1]"
    )

    POST_LIKE_BUTTON_LIKED = (
        "(//section[.//svg[@aria-label='Comentar' or @aria-label='Comment']]"
        "//span[contains(@class,'x1qfufaz')]"
        "//div[@role='button'][.//svg[@aria-label='Ya no me gusta' or @aria-label='Unlike']])[1]"
    )

    POST_MAIN_MEDIA_IMAGES = (
        "//article//div[contains(@class,'_aagu') and contains(@class,'_aato')]//img"
    )

    # =========================================================
    # JS FALLBACKS
    # =========================================================

    CLICK_FOLLOWERS_BUTTON_SCRIPT = r"""
    return (() => {
        const norm = (txt) => (txt || "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();

        const visible = (el) => {
            if (!el) return false;
            const st = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();

            return (
                st.display !== "none" &&
                st.visibility !== "hidden" &&
                r.width > 5 &&
                r.height > 5
            );
        };

        const header = document.querySelector("header") || document;

        const candidates = [
            ...header.querySelectorAll("a"),
            ...header.querySelectorAll("button"),
            ...header.querySelectorAll('[role="button"]'),
            ...header.querySelectorAll("div"),
            ...header.querySelectorAll("span")
        ].filter(visible);

        let target = null;

        for (const el of candidates) {
            const txt = norm(el.innerText || el.textContent || "");

            if (!txt) continue;

            const hasFollowers =
                txt.includes("seguidores") ||
                txt.includes("followers");

            const isFollowing =
                txt.includes("seguidos") ||
                txt.includes("following");

            if (!hasFollowers || isFollowing) continue;

            target = el;
            break;
        }

        if (!target) {
            return {
                ok: false,
                reason: "followers-target-not-found",
                total_candidates: candidates.length
            };
        }

        const clickable =
            target.closest("a") ||
            target.closest("button") ||
            target.closest('[role="button"]') ||
            target;

        clickable.scrollIntoView({
            block: "center",
            inline: "center"
        });

        const rect = clickable.getBoundingClientRect();

        if (!rect || rect.width <= 0 || rect.height <= 0) {
            return {
                ok: false,
                reason: "invalid-clickable-rect",
                text: norm(target.innerText || target.textContent || "")
            };
        }

        const x = Math.floor(rect.left + rect.width / 2);
        const y = Math.floor(rect.top + rect.height / 2);

        const topEl = document.elementFromPoint(x, y) || clickable;

        const finalTarget =
            topEl.closest("a") ||
            topEl.closest("button") ||
            topEl.closest('[role="button"]') ||
            clickable;

        const fireMouse = (el, type) => {
            try {
                el.dispatchEvent(new MouseEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: x,
                    clientY: y
                }));
            } catch (e) {}
        };

        const firePointer = (el, type) => {
            try {
                el.dispatchEvent(new PointerEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: x,
                    clientY: y,
                    pointerType: "mouse",
                    isPrimary: true
                }));
            } catch (e) {}
        };

        try {
            firePointer(finalTarget, "pointerover");
            fireMouse(finalTarget, "mouseover");
            firePointer(finalTarget, "pointerenter");
            fireMouse(finalTarget, "mouseenter");
            firePointer(finalTarget, "pointerdown");
            fireMouse(finalTarget, "mousedown");
            firePointer(finalTarget, "pointerup");
            fireMouse(finalTarget, "mouseup");
            fireMouse(finalTarget, "click");

            if (typeof finalTarget.click === "function") {
                finalTarget.click();
            }

            return {
                ok: true,
                reason: "clicked",
                text: norm(target.innerText || target.textContent || ""),
                clicked_tag: finalTarget.tagName,
                x,
                y
            };
        } catch (e) {
            return {
                ok: false,
                reason: "click-error",
                error: String(e),
                text: norm(target.innerText || target.textContent || "")
            };
        }
    })();
    """

    EXTRACT_REAL_FOLLOWERS_FROM_MODAL_SCRIPT = r"""
    return (() => {
        const dialog = document.querySelector('div[role="dialog"]');

        if (!dialog) {
            return {
                ok: false,
                reason: "dialog-not-found",
                followers: [],
                count: 0
            };
        }

        const norm = (txt) => (txt || "")
            .replace(/\s+/g, " ")
            .trim();

        const lower = (txt) => norm(txt).toLowerCase();

        const visible = (el) => {
            if (!el) return false;
            const st = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();

            return (
                st.display !== "none" &&
                st.visibility !== "hidden" &&
                r.width > 3 &&
                r.height > 3
            );
        };

        const isSuggestionText = (txt) => {
            const t = lower(txt);
            return (
                t.includes("sugerencias para ti") ||
                t.includes("suggestions for you")
            );
        };

        const suggestionCandidates = [
            ...dialog.querySelectorAll("h1,h2,h3,h4,h5,h6,span,div")
        ].filter((el) => isSuggestionText(el.innerText || el.textContent || ""));

        const suggestionHeader = suggestionCandidates.length
            ? suggestionCandidates[0]
            : null;

        const isAfterSuggestionHeader = (el) => {
            if (!suggestionHeader || !el) return false;

            try {
                return Boolean(
                    suggestionHeader.compareDocumentPosition(el) &
                    Node.DOCUMENT_POSITION_FOLLOWING
                );
            } catch (e) {
                return false;
            }
        };

        const isValidProfileHref = (href) => {
            if (!href) return false;

            try {
                const url = new URL(href, location.origin);
                const path = url.pathname || "";

                if (!path.startsWith("/")) return false;

                const clean = path.replace(/^\/+/, "").replace(/\/+$/, "");

                if (!clean) return false;
                if (clean.includes("/")) return false;

                const blocked = new Set([
                    "explore",
                    "reels",
                    "reel",
                    "p",
                    "stories",
                    "accounts",
                    "direct",
                    "about",
                    "developer",
                    "legal",
                    "web",
                    "tv"
                ]);

                if (blocked.has(clean.toLowerCase())) return false;

                return true;
            } catch (e) {
                return false;
            }
        };

        const anchors = [
            ...dialog.querySelectorAll('a[href^="/"]')
        ];

        const followers = [];
        const seen = new Set();

        for (const a of anchors) {
            if (!visible(a)) continue;

            if (isAfterSuggestionHeader(a)) {
                continue;
            }

            const hrefRaw = a.getAttribute("href") || "";

            if (!isValidProfileHref(hrefRaw)) continue;

            const url = new URL(hrefRaw, location.origin);
            const username = url.pathname
                .replace(/^\/+/, "")
                .replace(/\/+$/, "")
                .trim();

            if (!username) continue;

            const finalUrl = url.origin + "/" + username + "/";

            if (seen.has(finalUrl)) continue;
            seen.add(finalUrl);

            const text = norm(a.innerText || a.textContent || "");

            followers.push({
                username,
                url: finalUrl,
                text
            });
        }

        return {
            ok: true,
            reason: suggestionHeader ? "stopped-before-suggestions" : "no-suggestions-header",
            followers,
            count: followers.length,
            has_suggestions_header: Boolean(suggestionHeader)
        };
    })();
    """