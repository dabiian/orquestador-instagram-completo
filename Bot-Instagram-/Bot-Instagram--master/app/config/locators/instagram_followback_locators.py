class InstagramFollowbackLocators:
    # Fallbacks conservadores: Instagram cambia el SVG/clases, pero el control
    # de navegación suele conservar aria-label/role o un texto accesible.
    SEARCH_ICON_CSS = 'svg[aria-label="Búsqueda"], svg[aria-label="Search"], [aria-label="Búsqueda"], [aria-label="Search"]'
    SEARCH_NAV_JS = r"""
    return (() => {
        const norm = v => String(v || '').replace(/\\s+/g, ' ').trim().toLowerCase();
        const visible = el => {
            if (!el || !el.isConnected) return false;
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 &&
                   s.display !== 'none' && s.visibility !== 'hidden' &&
                   s.pointerEvents !== 'none' && Number(s.opacity) !== 0;
        };
        const labelMatch = /(\bbuscar\b|\bbúsqueda\b|\bsearch\b)/i;
        const candidates = [
            ...document.querySelectorAll('[aria-label]'),
            ...document.querySelectorAll('[role="button"]'),
            ...document.querySelectorAll('a[href]')
        ];
        const scored = [];
        for (const el of candidates) {
            if (!visible(el)) continue;
            const aria = norm(el.getAttribute('aria-label'));
            const title = norm(el.getAttribute('title'));
            const href = norm(el.getAttribute('href'));
            const txt = norm(el.textContent);
            let score = 0;
            if (labelMatch.test(aria)) score += 100;
            if (labelMatch.test(title)) score += 80;
            if ((el.getAttribute('role') || '').toLowerCase() === 'button' && labelMatch.test(txt)) score += 60;
            if (href === '/search/' || href.endsWith('/search/')) score += 90;
            if (aria.includes('search')) score += 20;
            if (score > 0) scored.push([score, el]);
        }
        scored.sort((a,b) => b[0] - a[0]);
        return scored.length ? scored[0][1] : null;
    })();
    """


    SEARCH_INPUT = (
        "//input[@aria-label='Buscar entrada' or @aria-label='Search input' "
        "or @placeholder='Busca' or @placeholder='Search' or "
        "@name='searchQuery' or @name='search' or @type='text']"
    )

    # Instagram cambia con frecuencia aria-label/placeholder del buscador.
    # Se usan fallbacks CSS simples antes de recurrir al Self-Healer.
    SEARCH_INPUT_FALLBACK_CSS = [
        "input[aria-label='Search input']",
        "input[aria-label='Buscar entrada']",
        "input[placeholder='Search']",
        "input[placeholder='Busca']",
        "input[name='searchQuery']",
        "input[name='search']",
        "input[type='text']",
    ]

    HASHTAG_SEARCH_RESULTS = (
        "//a[contains(@href, '/explore/tags/')]"
    )

    HASHTAG_GRID_POSTS = (
        "//a[@role='link' and (starts-with(@href, '/p/') or starts-with(@href, '/reel/'))]"
    )

    # CAPTION DEL POST, no comentario real
    POST_CAPTION_BLOCK = "//ul[contains(@class,'_a9z6') and contains(@class,'_a9za')]"
    POST_CAPTION_TEXT = (
        "//ul[contains(@class,'_a9z6') and contains(@class,'_a9za')]"
        "//h1[contains(@class,'_ap3a')]"
    )

    # COMENTARIOS REALES
    COMMENTS_ROOT = "//ul[contains(@class,'_a9ym')]"

    COMMENT_ITEMS = (
        "//ul[contains(@class,'_a9ym')]"
        "//li[contains(@class,'_a9zj') and contains(@class,'_a9zl')]"
    )

    COMMENT_USERNAME_REL = ".//h3//a[@href and @role='link']"

    COMMENT_TEXT_REL = (
        ".//h3/following-sibling::div[1]"
        "//span[contains(@class,'_ap3a') or contains(@class,'_aaco')]"
    )

    COMMENT_REPLY_BUTTON_REL = (
        ".//button[.//span[normalize-space()='Responder' or normalize-space()='Reply']]"
    )

    COMMENT_TIME_REL = ".//a[contains(@href,'/c/') and .//time]//time"

    COMMENT_PERMALINK_REL = ".//a[contains(@href,'/c/') and .//time]"

    COMMENT_OPTIONS_REL = (
        ".//*[name()='svg' and "
        "(@aria-label='Opciones del comentario' or @aria-label='Comment options')]"
        "/ancestor::*[@role='button'][1]"
    )

    VIEW_REPLIES_BUTTONS = (
        "//button[.//span[contains(normalize-space(),'Ver respuestas') "
        "or contains(normalize-space(),'View replies')]]"
    )

    CLOSE_POST_BUTTON = (
        "//*[name()='svg' and (@aria-label='Cerrar' or @aria-label='Close' "
        "or .//title[normalize-space()='Cerrar'] or .//title[normalize-space()='Close'])]"
        "/ancestor::*[@role='button'][1]"
    )

    LOAD_MORE_COMMENTS_BTN = (
        "//button[@type='button' and ("
        ".//svg[@aria-label='Cargar más comentarios'] or "
        ".//title[normalize-space()='Cargar más comentarios'] or "
        ".//svg[@aria-label='Load more comments'] or "
        ".//title[normalize-space()='Load more comments']"
        ")]"
    )

    POST_ARTICLE = "//article"

    POST_AUTHOR_USERNAME = (
        "//article//header//a[starts-with(@href,'/') and normalize-space()!=''][1]"
    )

    POST_AUTHOR_PROFILE_HREF = (
        "//article//header//a[starts-with(@href,'/') and normalize-space()!=''][1]"
    )

    POST_CAPTION = (
        "//article//h1[normalize-space()]"
    )


    # =========================================================
    # PROFILE / FOLLOW BUTTONS
    # =========================================================

    PROFILE_FOLLOW_BUTTON = (
        "//header//*[self::button or @role='button']"
        "[normalize-space()='Seguir' or normalize-space()='Follow' "
        "or .//*[normalize-space()='Seguir' or normalize-space()='Follow']]"
    )

    PROFILE_FOLLOWING_STATE_BUTTON = (
        "//header//*[self::button or @role='button']"
        "[normalize-space()='Siguiendo' or normalize-space()='Following' "
        "or normalize-space()='Solicitado' or normalize-space()='Requested' "
        "or .//*[normalize-space()='Siguiendo' or normalize-space()='Following' "
        "or normalize-space()='Solicitado' or normalize-space()='Requested']]"
    )


    # =========================================================
    # COMMENTS / REPLIES
    # =========================================================

    COMMENT_ROOT_REL = "ancestor-or-self::li[1]"

    REPLY_INPUT_BOXES = [
        "//form//textarea",
        "//form//div[@role='textbox' and @contenteditable='true']",
        "//article//textarea",
        "//article//div[@role='textbox' and @contenteditable='true']",
        "//div[@role='dialog']//textarea",
        "//div[@role='dialog']//div[@role='textbox' and @contenteditable='true']",
    ]

    REPLY_SUBMIT_BUTTONS = [
        "//div[@role='button'][normalize-space()='Publicar' or normalize-space()='Post']",
        "//button[normalize-space()='Publicar' or normalize-space()='Post']",
        "//button[.//*[normalize-space()='Publicar' or normalize-space()='Post']]",
    ]

    COMMENT_ROOT_FROM_PERMALINK = "//a[contains(@href,'/c/')]/ancestor::li[1]"
    COMMENT_ROOT_LINKS_REL = ".//a[@href]"

    SCROLL_INTO_VIEW_CENTER_SCRIPT = (
        "arguments[0].scrollIntoView({block:'center', inline:'center'});"
    )

    SCROLL_INTO_VIEW_END_SCRIPT = (
        "arguments[0].scrollIntoView({block:'end', inline:'nearest'});"
    )

    CLICK_ELEMENT_SCRIPT = "arguments[0].click();"

    CLICK_LOAD_MORE_COMMENTS_SCRIPT = r"""
    return (() => {
        const selector = [
            'svg[aria-label="Cargar más comentarios"]',
            'svg[aria-label="Load more comments"]',
            'svg[aria-label="Ver más comentarios"]'
        ].join(",");

        const svg = document.querySelector(selector);

        if (!svg) {
            return { ok: false, reason: "svg-not-found" };
        }

        const btn = svg.closest("button");

        if (!btn) {
            return { ok: false, reason: "button-not-found" };
        }

        btn.scrollIntoView({ block: "center", behavior: "instant" });
        btn.click();

        return { ok: true, reason: "clicked" };
    })();
    """

    CLICK_LIKE_ON_COMMENT_SCRIPT = r"""
    const profileHrefRaw = arguments[0];
    const permalinkRaw = arguments[1];

    const norm = (href) => {
        if (!href) return "";
        return String(href)
            .replace(location.origin, "")
            .trim()
            .replace(/\/+$/, "") + "/";
    };

    const profileHref = norm(profileHrefRaw);
    const permalink = norm(permalinkRaw);

    const findExactCommentRoot = () => {
        let permalinkAnchor = null;

        if (permalink) {
            permalinkAnchor = [...document.querySelectorAll('a[href*="/p/"][href*="/c/"]')].find(a => {
                const h = norm(a.getAttribute("href") || a.href || "");
                return h === permalink;
            });
        }

        let userAnchor = [...document.querySelectorAll("a[href]")].find(a => {
            const h = norm(a.getAttribute("href") || a.href || "");
            return h === profileHref;
        });

        const seeds = [permalinkAnchor, userAnchor].filter(Boolean);

        for (const seed of seeds) {
            let current = seed;

            for (let level = 0; level < 15 && current; level++) {
                const hasExactPermalink = permalink
                    ? !![...current.querySelectorAll('a[href*="/p/"][href*="/c/"]')].find(a => {
                        const h = norm(a.getAttribute("href") || a.href || "");
                        return h === permalink;
                    })
                    : true;

                const hasExactUser = !![...current.querySelectorAll("a[href]")].find(a => {
                    const h = norm(a.getAttribute("href") || a.href || "");
                    return h === profileHref;
                });

                const likeButton =
                    current.querySelector('span._a9zu div[role="button"]') ||
                    current.querySelector('div[role="button"] svg[aria-label="Me gusta"]')?.closest('div[role="button"]') ||
                    current.querySelector('div[role="button"] svg[aria-label="Like"]')?.closest('div[role="button"]') ||
                    current.querySelector('div[role="button"] svg[aria-label="Ya no me gusta"]')?.closest('div[role="button"]') ||
                    current.querySelector('div[role="button"] svg[aria-label="Unlike"]')?.closest('div[role="button"]');

                if (hasExactPermalink && hasExactUser && likeButton) {
                    return current;
                }

                current = current.parentElement;
            }
        }

        return null;
    };

    const root = findExactCommentRoot();

    if (!root) {
        return { ok: false, reason: "root-not-found", profileHref, permalink };
    }

    const likeBtn =
        root.querySelector('span._a9zu div[role="button"]') ||
        root.querySelector('div[role="button"] svg[aria-label="Me gusta"]')?.closest('div[role="button"]') ||
        root.querySelector('div[role="button"] svg[aria-label="Like"]')?.closest('div[role="button"]') ||
        root.querySelector('div[role="button"] svg[aria-label="Ya no me gusta"]')?.closest('div[role="button"]') ||
        root.querySelector('div[role="button"] svg[aria-label="Unlike"]')?.closest('div[role="button"]');

    if (!likeBtn) {
        return { ok: false, reason: "like-not-found", profileHref, permalink };
    }

    const isAlreadyLiked =
        !!likeBtn.querySelector('svg[aria-label="Ya no me gusta"]') ||
        !!likeBtn.querySelector('svg[aria-label="Unlike"]') ||
        !!likeBtn.querySelector('title') &&
        ["Ya no me gusta", "Unlike"].includes((likeBtn.querySelector('title')?.textContent || "").trim());

    if (isAlreadyLiked) {
        return { ok: true, reason: "already-liked", profileHref, permalink };
    }

    likeBtn.scrollIntoView({ block: "center", inline: "center" });
    likeBtn.dispatchEvent(new MouseEvent("mouseover", { bubbles: true, cancelable: true }));
    likeBtn.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true, cancelable: true }));
    likeBtn.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    likeBtn.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
    likeBtn.click();

    return { ok: true, reason: "clicked", profileHref, permalink };
    """

    VISIBLE_COMMENTS_V2_SCRIPT = r"""
    return (() => {
        const norm = (txt) => (txt || '').replace(/\s+/g, ' ').trim();

        const isVisible = (el) => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return (
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                rect.width > 0 &&
                rect.height > 0
            );
        };

        const rows = [];
        const seen = new Set();

        const commentLis = [
            ...document.querySelectorAll('ul._a9ym li._a9zj'),
            ...document.querySelectorAll('ul._a9ym li'),
        ];

        for (const li of commentLis) {
            try {
                if (!li || !isVisible(li)) continue;

                const userAnchor =
                    li.querySelector('h3 a[href^="/"]') ||
                    li.querySelector('a[href^="/"]');

                const username = norm(userAnchor?.textContent || "");
                const profileHrefRaw = userAnchor?.getAttribute("href") || "";
                const profileHref = profileHrefRaw
                    ? new URL(profileHrefRaw, location.origin).href
                    : "";

                const textEl =
                    li.querySelector('span._ap3a[dir="auto"]') ||
                    li.querySelector('span._ap3a') ||
                    li.querySelector('h3 + div span[dir="auto"]');

                const text = norm(textEl?.textContent || "");

                const permalinkAnchor = li.querySelector('a[href*="/p/"][href*="/c/"], a[href*="/reel/"][href*="/c/"]');
                const permalinkRaw = permalinkAnchor?.getAttribute("href") || "";
                const permalink = permalinkRaw
                    ? new URL(permalinkRaw, location.origin).href
                    : "";

                const timeEl = li.querySelector('a[href*="/c/"] time, time');
                const timeText = norm(timeEl?.textContent || "");

                const nodeText = norm(li.textContent || "").toLowerCase();

                const hasReplyButton =
                    nodeText.includes("responder") ||
                    nodeText.includes("reply");

                const hasOptions =
                    !!li.querySelector('svg[aria-label="Opciones del comentario"]') ||
                    !!li.querySelector('svg[aria-label="Comment options"]');

                if (!username || !text) continue;

                if (li.querySelector("h2") && !permalink) continue;

                const key = `${profileHref}|${permalink}|${text}`;
                if (seen.has(key)) continue;
                seen.add(key);

                rows.push({
                    username,
                    text,
                    profile_href: profileHref,
                    permalink,
                    time_text: timeText,
                    has_reply_button: hasReplyButton,
                    has_options: hasOptions,
                });
            } catch (e) {}
        }

        return rows;
    })();
    """


    # =========================================================
    # NAVIGATION / SEARCH / HASHTAG GRID
    # =========================================================

    # Only real interactive ancestors are accepted. Generic div/span
    # fallbacks were too permissive and could select a container underneath
    # an overlay, producing misleading click/self-healing failures.
    SEARCH_CLICKABLE_ANCESTORS = [
        "./ancestor::*[@role='button'][1]",
        "./ancestor::button[1]",
        "./ancestor::a[1]",
    ]

    HASHTAG_RESULT_URL_PART = "/explore/tags/"

    HASHTAG_GRID_VALID_POST_URL_PARTS = [
        "/p/",
        "/reel/",
    ]

    HASHTAG_GRID_INVALID_POST_URL_PARTS = [
        "/c/",
    ]

    PROFILE_BLOCKING_URL_PARTS = [
        "/p/",
        "/reel/",
        "/explore/tags/",
    ]

    PROFILE_HEADER = "//header"

    SCROLL_GRID_POST_CENTER_SCRIPT = (
        "arguments[0].scrollIntoView({block:'center', inline:'center'});"
    )