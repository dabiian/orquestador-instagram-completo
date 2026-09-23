class InstagramProfileLocators:
    """
    Locators/scripts centralizados para perfiles, grids, posts abiertos,
    comentarios y acciones sobre comentarios.

    Usado por:
    - ShareInstagramCuratedPostTask
    - InteractWithOwnerLatestPostTask
    - InstagramProspectDiscoveryTask
    - InteractWithOwnPostsTask
    """

    # =========================================================
    # PROFILE / HOME
    # =========================================================

    HOME_PAGE = "https://www.instagram.com/"

    MY_PROFILE_LINK = (
        "//a[@role='link' and @href and "
        "("
        ".//*[normalize-space()='Perfil'] "
        "or .//*[normalize-space()='Profile'] "
        "or @aria-label='Perfil' "
        "or @aria-label='Profile' "
        "or .//*[name()='svg' and (@aria-label='Perfil' or @aria-label='Profile')]"
        ")]"
    )

    PROFILE_POST_LINKS = (
        "//a[contains(@href,'/p/') "
        "or contains(@href,'/reel/') "
        "or contains(@href,'/tv/')]"
    )

    POST_URL_PARTS = ["/p/", "/reel/", "/reels/", "/tv/"]

    # =========================================================
    # BASIC JS HELPERS
    # =========================================================

    CLICK_ELEMENT_SCRIPT = "arguments[0].click();"

    SCROLL_INTO_VIEW_CENTER_SCRIPT = (
        "arguments[0].scrollIntoView({block:'center', inline:'center'});"
    )

    SCROLL_INTO_VIEW_END_SCRIPT = (
        "arguments[0].scrollIntoView({block:'end', inline:'nearest'});"
    )

    SCROLL_PROFILE_GRID_SCRIPT = (
        "window.scrollBy(0, Math.floor(window.innerHeight * 0.95));"
    )

    SCROLL_TO_BOTTOM_SCRIPT = "window.scrollTo(0, document.body.scrollHeight);"

    # =========================================================
    # FOLLOW / FOLLOWING
    # =========================================================

    PROFILE_FOLLOW_BUTTONS = [
        "//button[normalize-space(.)='Seguir']",
        "//button[normalize-space(.)='Follow']",
        "//button[.//div[normalize-space()='Seguir']]",
        "//button[.//div[normalize-space()='Follow']]",
        "//*[@role='button' and normalize-space(.)='Seguir']",
        "//*[@role='button' and normalize-space(.)='Follow']",
        "//*[@role='button' and .//div[normalize-space()='Seguir']]",
        "//*[@role='button' and .//div[normalize-space()='Follow']]",
    ]

    PROFILE_FOLLOWING_STATE_BUTTONS = [
        "//button[normalize-space(.)='Siguiendo']",
        "//button[normalize-space(.)='Following']",
        "//button[normalize-space(.)='Solicitado']",
        "//button[normalize-space(.)='Requested']",
        "//button[normalize-space(.)='Pendiente']",
        "//button[normalize-space(.)='Pending']",
        "//button[.//div[normalize-space()='Siguiendo']]",
        "//button[.//div[normalize-space()='Following']]",
        "//button[.//div[normalize-space()='Solicitado']]",
        "//button[.//div[normalize-space()='Requested']]",
        "//button[.//div[normalize-space()='Pendiente']]",
        "//button[.//div[normalize-space()='Pending']]",
        "//*[@role='button' and normalize-space(.)='Siguiendo']",
        "//*[@role='button' and normalize-space(.)='Following']",
        "//*[@role='button' and normalize-space(.)='Solicitado']",
        "//*[@role='button' and normalize-space(.)='Requested']",
        "//*[@role='button' and normalize-space(.)='Pendiente']",
        "//*[@role='button' and normalize-space(.)='Pending']",
        "//*[@role='button' and .//div[normalize-space()='Siguiendo']]",
        "//*[@role='button' and .//div[normalize-space()='Following']]",
        "//*[@role='button' and .//div[normalize-space()='Solicitado']]",
        "//*[@role='button' and .//div[normalize-space()='Requested']]",
        "//*[@role='button' and .//div[normalize-space()='Pendiente']]",
        "//*[@role='button' and .//div[normalize-space()='Pending']]",
    ]

    # =========================================================
    # OPENED POST READ - GENERAL
    # =========================================================

    OPENED_POST_TEXT_CONTEXT_SCRIPT = """
    return (() => {
        const norm = (txt) => (txt || '').replace(/\\s+/g, ' ').trim();

        const texts = [];

        const h1Candidates = [
            ...document.querySelectorAll('article h1'),
            ...document.querySelectorAll('main article h1')
        ];

        for (const node of h1Candidates) {
            const value = norm(node.textContent || '');
            if (value && value.length > 3) {
                texts.push(value);
            }
        }

        const metaDesc = document.querySelector('meta[property="og:description"]');
        const metaText = norm(metaDesc?.getAttribute('content') || '');
        if (metaText && metaText.length > 3) {
            texts.push(metaText);
        }

        const imageAlts = [
            ...document.querySelectorAll('article img[alt]'),
            ...document.querySelectorAll('main img[alt]')
        ]
        .map(img => norm(img.getAttribute('alt') || ''))
        .filter(Boolean)
        .filter(txt => txt.length > 8)
        .slice(0, 3);

        texts.push(...imageAlts);

        return [...new Set(texts)].slice(0, 8).join(" | ");
    })();
    """

    OPENED_POST_AUTHOR_USERNAME_SCRIPT = """
    return (() => {
        const a =
            document.querySelector('article header a[href^="/"]') ||
            document.querySelector('header a[href^="/"]');

        const href = (a?.getAttribute('href') || '').trim();
        if (!href) return "";

        return href.replace(/^\\//, '').replace(/\\/$/, '').split('/')[0];
    })();
    """

    CURRENT_POST_CONTEXT_SCRIPT = """
    return (() => {
        const norm = (txt) => (txt || '').replace(/\\s+/g, ' ').trim();

        const currentUrl = location.href;

        const authorAnchor =
            document.querySelector('article header a[href^="/"]') ||
            document.querySelector('header a[href^="/"]');

        const authorHrefRaw = authorAnchor?.getAttribute('href') || '';
        const authorProfileUrl = authorHrefRaw
            ? new URL(authorHrefRaw, location.origin).href
            : '';

        const authorUsername = authorHrefRaw
            ? authorHrefRaw.replace(/^\\//, '').replace(/\\/$/, '').split('/')[0]
            : '';

        const captionCandidates = [
            'article h1',
            'article div[role="dialog"] h1',
            'main h1',
            'article span[dir="auto"]',
        ];

        let captionText = '';

        for (const selector of captionCandidates) {
            const nodes = [...document.querySelectorAll(selector)];
            const texts = nodes
                .map(n => norm(n.textContent))
                .filter(Boolean);

            if (texts.length) {
                texts.sort((a, b) => b.length - a.length);
                captionText = texts[0];
                break;
            }
        }

        if (!captionText) {
            const metaDesc = document.querySelector('meta[property="og:description"]');
            const metaContent = norm(metaDesc?.getAttribute('content') || '');
            if (metaContent) {
                captionText = metaContent;
            }
        }

        let postType = 'post';
        if (currentUrl.includes('/reel/') || currentUrl.includes('/reels/')) {
            postType = 'reel';
        }

        return {
            post_url: currentUrl,
            opened_href: arguments[0] || currentUrl,
            author_username: authorUsername,
            author_profile_url: authorProfileUrl,
            caption_text: captionText,
            post_type: postType
        };
    })();
    """

    RECENT_POST_CONTEXT_SCRIPT = """
    return (() => {
        const norm = (txt) => (txt || '').replace(/\\s+/g, ' ').trim();

        const currentUrl = location.href;
        let captionText = '';

        const authorAnchor =
            document.querySelector('article header a[href^="/"]') ||
            document.querySelector('div[role="dialog"] article header a[href^="/"]') ||
            document.querySelector('header a[href^="/"]');

        const authorHrefRaw = (authorAnchor?.getAttribute('href') || '').trim();
        let authorUsername = '';
        let authorProfileUrl = '';

        if (authorHrefRaw) {
            try {
                const authorUrl = new URL(authorHrefRaw, location.origin);
                const parts = authorUrl.pathname.split('/').filter(Boolean);
                if (parts.length === 1) {
                    authorUsername = norm(parts[0]).toLowerCase().replace(/^@/, '');
                    authorProfileUrl = authorUrl.origin + '/' + parts[0] + '/';
                }
            } catch {}
        }

        const captionCandidates = [
            'article h1',
            'div[role="dialog"] article h1',
            'main h1',
            'article span[dir="auto"]',
            'main span[dir="auto"]'
        ];

        for (const selector of captionCandidates) {
            const nodes = [...document.querySelectorAll(selector)];
            const texts = nodes
                .map(n => norm(n.textContent))
                .filter(Boolean);

            if (texts.length) {
                texts.sort((a, b) => b.length - a.length);
                captionText = texts[0];
                break;
            }
        }

        if (!captionText) {
            const metaDesc = document.querySelector('meta[property="og:description"]');
            const metaContent = norm(metaDesc?.getAttribute('content') || '');
            if (metaContent) captionText = metaContent;
        }

        let postType = 'post';
        if (currentUrl.includes('/reel/') || currentUrl.includes('/reels/')) {
            postType = 'reel';
        }

        return {
            post_url: currentUrl,
            author_username: authorUsername,
            author_profile_url: authorProfileUrl,
            caption_text: captionText,
            post_type: postType
        };
    })();
    """

    # =========================================================
    # PROFILE CONTEXT
    # =========================================================

    AUTHOR_PROFILE_CONTEXT_SCRIPT = """
    return (() => {
        const norm = (txt) => (txt || '').replace(/\\s+/g, ' ').trim();

        let displayName = '';
        let bio = '';

        const displayCandidates = [
            ...document.querySelectorAll('header h1'),
            ...document.querySelectorAll('header h2'),
        ].map(n => norm(n.textContent)).filter(Boolean);

        if (displayCandidates.length) {
            displayName = displayCandidates[0];
        }

        const bioCandidates = [
            ...document.querySelectorAll('header section div'),
            ...document.querySelectorAll('header section span'),
            ...document.querySelectorAll('header div'),
            ...document.querySelectorAll('header span'),
        ]
        .map(n => norm(n.textContent))
        .filter(Boolean)
        .filter(txt =>
            txt.length > 5 &&
            !/^\\d+$/.test(txt) &&
            !txt.includes('publicaciones') &&
            !txt.includes('followers') &&
            !txt.includes('seguidos') &&
            !txt.includes('posts') &&
            !txt.includes('following')
        );

        if (bioCandidates.length) {
            bio = bioCandidates.slice(0, 5).join(' | ');
        }

        return {
            display_name: displayName,
            bio: bio,
            profile_url: location.href
        };
    })();
    """

    # =========================================================
    # PROFILE GRID JS
    # =========================================================

    PROFILE_GRID_POST_TARGETS_SCRIPT = """
    return (() => {
        // Instagram post URLs do NOT encode the owning username.  The old
        // implementation incorrectly parsed the first path segment as a
        // username, which could admit/omit unrelated targets depending on
        // the DOM shape.  Ownership is now verified after opening the post.
        const selectors = [
            'article a[href]',
            'main a[href^="/p/"]',
            'main a[href^="/reel/"]',
            'main a[href^="/tv/"]'
        ];

        const out = [];
        const seen = new Set();

        for (const selector of selectors) {
            for (const a of document.querySelectorAll(selector)) {
                try {
                    const raw = (a.getAttribute('href') || '').trim();
                    if (!raw) continue;

                    const url = new URL(raw, window.location.origin);
                    const parts = url.pathname.split('/').filter(Boolean);
                    if (parts.length < 2) continue;

                    const contentType = String(parts[0] || '').toLowerCase();
                    const shortcode = String(parts[1] || '').trim();
                    if (!['p', 'reel', 'tv'].includes(contentType) || !shortcode) continue;

                    const canonical =
                        'https://www.instagram.com/' + contentType + '/' + shortcode + '/';

                    if (!seen.has(canonical)) {
                        seen.add(canonical);
                        out.push(canonical);
                    }
                } catch {}
            }
        }

        return out;
    })();
    """
    # =========================================================
    # OWN POST SURFACE
    # =========================================================

    POST_SURFACE_STATE_SCRIPT = r"""
    return (() => {
        const q = (sel) => document.querySelector(sel);
        const qa = (sel) => document.querySelectorAll(sel);

        const hasImage =
            !!q('img[alt*="Photo by @"]') ||
            !!q('article img') ||
            !!q('img');

        const hasCaption =
            !!q('ul._a9z6 li h1._ap3a') ||
            !!q('h1._ap3a') ||
            !!q('article h1');

        const hasCommentPermalinks = qa('a[href*="/c/"]').length > 0;

        const hasCommentBox =
            !!q('textarea[placeholder*="Añade un comentario"]') ||
            !!q('textarea[aria-label*="Añade un comentario"]') ||
            !!q('textarea[placeholder*="Add a comment"]') ||
            !!q('textarea[aria-label*="Add a comment"]');

        return {
            hasImage,
            hasCaption,
            hasCommentPermalinks,
            hasCommentBox,
            currentUrl: location.href
        };
    })();
    """

    OWN_CURRENT_POST_CONTEXT_SCRIPT = r"""
    return (() => {
        const norm = (txt) => (txt || '').replace(/\s+/g, ' ').trim();

        const data = {
            url: location.href,
            author_username: "",
            caption: "",
            media_alt: "",
            media_src: ""
        };

        const img =
            document.querySelector('img[alt*="Photo by @"]') ||
            document.querySelector('article img') ||
            document.querySelector('img');

        if (img) {
            data.media_alt = norm(img.getAttribute('alt') || '');
            data.media_src = img.getAttribute('src') || '';

            const m = data.media_alt.match(/Photo by @([A-Za-z0-9._]+)/i);
            if (m) {
                data.author_username = m[1];
            }
        }

        if (!data.author_username) {
            const ownerEl =
                document.querySelector('ul._a9z6 li h2 a[href^="/"]') ||
                document.querySelector('header h2 a[href^="/"]') ||
                document.querySelector('header a[href^="/"]');

            if (ownerEl) {
                data.author_username = norm(ownerEl.textContent)
                    .replace(/^@/, '')
                    .replace(/\/$/, '');
            }
        }

        const captionEl =
            document.querySelector('ul._a9z6 li h1._ap3a[dir="auto"]') ||
            document.querySelector('ul._a9z6 li h1._ap3a') ||
            document.querySelector('h1._ap3a[dir="auto"]') ||
            document.querySelector('h1._ap3a') ||
            document.querySelector('article h1');

        if (captionEl) {
            data.caption = norm(captionEl.textContent);
        }

        return data;
    })();
    """

    # =========================================================
    # OWN POST COMMENTS
    # =========================================================

    VISIBLE_COMMENTS_SCRIPT = r"""
    return (() => {
        const norm = (txt) => (txt || '').replace(/\s+/g, ' ').trim();

        const data = {
            url: location.href,
            comments_count: 0,
            comments: []
        };

        const roots = [...document.querySelectorAll('a[href*="/c/"]')]
            .map(a => a.closest('li'))
            .filter(Boolean);

        const seen = new Set();

        for (const li of roots) {
            const userAnchor =
                li.querySelector('h3 a[href^="/"]') ||
                li.querySelector('a[href^="/"]');

            const username = norm(userAnchor?.textContent || '');

            const profile_href = userAnchor
                ? new URL(userAnchor.getAttribute('href'), location.origin).href
                : '';

            const permalinkAnchor = li.querySelector('a[href*="/c/"]');

            const permalink = permalinkAnchor
                ? new URL(permalinkAnchor.getAttribute('href'), location.origin).href
                : '';

            const textCandidates = [
                ...li.querySelectorAll('span._ap3a[dir="auto"]'),
                ...li.querySelectorAll('span._ap3a'),
                ...li.querySelectorAll('span[dir="auto"]')
            ];

            let text = '';

            for (const el of textCandidates) {
                const t = (el.textContent || '').replace(/\s+/g, ' ').trim();
                const tl = t.toLowerCase();

                if (!t) continue;

                if ([
                    'responder',
                    'reply',
                    'ver traducción',
                    'see translation',
                    'me gusta',
                    'like'
                ].includes(tl)) continue;

                if (username && t === username) continue;

                text = t;
                break;
            }

            const has_reply_button = !![...li.querySelectorAll('button, [role="button"]')]
                .find(btn => {
                    const txt = norm(btn.innerText || btn.textContent || '').toLowerCase();
                    return txt === 'responder' || txt === 'reply';
                });

            const has_like_button = !!li.querySelector(
                'svg[aria-label="Me gusta"], svg[aria-label="Like"]'
            );

            if (!username || !text) continue;

            const key = `${profile_href}|${permalink}|${text}`;

            if (seen.has(key)) continue;
            seen.add(key);

            data.comments.push({
                username,
                text,
                profile_href,
                permalink,
                has_reply_button,
                has_like_button
            });
        }

        data.comments_count = data.comments.length;
        return data;
    })();
    """

    FIND_COMMENT_ROOT_SCRIPT = r"""
    return (() => {
        const profileHrefRaw = arguments[0] || "";
        const permalinkRaw = arguments[1] || "";
        const textRaw = arguments[2] || "";

        const normText = (txt) => String(txt || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();

        const normHref = (href) => {
            if (!href) return "";
            return String(href)
                .replace(location.origin, "")
                .trim()
                .replace(/\/+$/, "") + "/";
        };

        const profileHref = normHref(profileHrefRaw);
        const permalink = normHref(permalinkRaw);
        const targetText = normText(textRaw);

        const candidates = [...document.querySelectorAll('a[href*="/c/"]')]
            .map(a => a.closest('li'))
            .filter(Boolean);

        for (const root of candidates) {
            const rootText = normText(root.innerText || root.textContent || "");

            const hrefs = [...root.querySelectorAll("a[href]")]
                .map(a => normHref(a.getAttribute("href") || a.href || ""))
                .filter(Boolean);

            const hasProfile = profileHref && hrefs.includes(profileHref);
            const hasPermalink = permalink && hrefs.includes(permalink);

            if (hasPermalink) return root;

            if (hasProfile && targetText && rootText.includes(targetText)) {
                return root;
            }

            if (targetText && rootText.includes(targetText)) {
                return root;
            }
        }

        return null;
    })();
    """

    LOAD_MORE_COMMENTS_BUTTONS = [
        "//button[normalize-space()='Ver más comentarios']",
        "//button[normalize-space()='Load more comments']",
        "//button[contains(., 'Ver más comentarios')]",
        "//button[contains(., 'Load more comments')]",
        "//button[contains(., 'View all')]",
        "//*[@role='button' and contains(., 'Ver más comentarios')]",
        "//*[@role='button' and contains(., 'Load more comments')]",
        "//*[@role='button' and contains(., 'View all')]",
    ]

    CLICK_LIKE_ON_COMMENT_SCRIPT = r"""
    const root = arguments[0];

    if (!root) {
        return { ok: false, reason: 'no-root' };
    }

    const likedSvg = root.querySelector(
        'svg[aria-label="Ya no me gusta"], svg[aria-label="Unlike"]'
    );

    if (likedSvg) {
        return { ok: true, reason: 'already-liked' };
    }

    const likeSvg = root.querySelector(
        'svg[aria-label="Me gusta"], svg[aria-label="Like"]'
    );

    if (!likeSvg) {
        return { ok: false, reason: 'like-svg-not-found' };
    }

    const button = likeSvg.closest('[role="button"], button, div');

    if (!button) {
        return { ok: false, reason: 'button-not-found' };
    }

    button.scrollIntoView({ block: "center", inline: "center" });
    button.dispatchEvent(new MouseEvent("mouseover", { bubbles: true, cancelable: true }));
    button.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true, cancelable: true }));
    button.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    button.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
    button.click();

    return { ok: true, reason: 'clicked' };
    """

    REPLY_BUTTON_REL_XPATH = (
        ".//button[normalize-space()='Responder' or normalize-space()='Reply']"
        "|.//*[@role='button' and (normalize-space()='Responder' or normalize-space()='Reply')]"
    )

    REPLY_INPUT_BOXES = [
        "//textarea[contains(@placeholder,'Añade un comentario')]",
        "//textarea[contains(@aria-label,'Añade un comentario')]",
        "//textarea[contains(@placeholder,'Add a comment')]",
        "//textarea[contains(@aria-label,'Add a comment')]",
    ]

    WRITE_REPLY_WITH_EMOJIS_SCRIPT = r"""
    const el = arguments[0];
    const text = arguments[1];

    if (!el) return false;

    el.focus();

    const proto =
        el.tagName === 'TEXTAREA'
            ? window.HTMLTextAreaElement.prototype
            : window.HTMLInputElement.prototype;

    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
    const setter = descriptor && descriptor.set;

    if (setter) {
        setter.call(el, text);
    } else {
        el.value = text;
    }

    el.dispatchEvent(new InputEvent('input', {
        bubbles: true,
        cancelable: true,
        data: text,
        inputType: 'insertText'
    }));

    el.dispatchEvent(new Event('change', {
        bubbles: true
    }));

    el.dispatchEvent(new KeyboardEvent('keydown', {
        bubbles: true,
        cancelable: true,
        key: 'Process'
    }));

    el.dispatchEvent(new KeyboardEvent('keyup', {
        bubbles: true,
        cancelable: true,
        key: 'Process'
    }));

    return el.value;
    """

    REDISPATCH_REPLY_INPUT_EVENTS_SCRIPT = r"""
    const el = arguments[0];
    const current = el.value || '';

    el.dispatchEvent(new InputEvent('input', {
        bubbles: true,
        cancelable: true,
        data: current,
        inputType: 'insertText'
    }));

    el.dispatchEvent(new Event('change', { bubbles: true }));
    """

    GET_REPLY_PUBLISH_BUTTON_SCRIPT = r"""
    const input = arguments[0];

    if (!input) return null;

    const form = input.closest('form') || document;

    const norm = (txt) => (txt || '')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase();

    const candidates = [
        ...form.querySelectorAll('button'),
        ...form.querySelectorAll('[role="button"]'),
        ...form.querySelectorAll('div[role="button"]')
    ];

    for (const el of candidates) {
        const text = norm(el.innerText || el.textContent || '');

        if (!(text.includes('publicar') || text.includes('post'))) continue;

        return el;
    }

    return null;
    """


    EXTRACT_REAL_FOLLOWERS_FROM_MODAL_SCRIPT = r"""
    return (() => {
        const dialog = document.querySelector('div[role="dialog"]');

        if (!dialog) {
            return {
                ok: false,
                reason: "dialog-not-found",
                followers: []
            };
        }

        const norm = (txt) => (txt || "")
            .replace(/\s+/g, " ")
            .trim();

        const normLower = (txt) => norm(txt).toLowerCase();

        const isValidProfileHref = (href) => {
            if (!href) return false;

            try {
                const url = new URL(href, location.origin);
                const path = url.pathname || "";

                if (!path.startsWith("/")) return false;

                const clean = path.replace(/^\/+/, "").replace(/\/+$/, "");

                if (!clean) return false;

                if (clean.includes("/")) return false;

                const blocked = [
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
                    "web"
                ];

                if (blocked.includes(clean.toLowerCase())) return false;

                return true;
            } catch (e) {
                return false;
            }
        };

        const isSuggestionsText = (txt) => {
            const t = normLower(txt);
            return (
                t.includes("sugerencias para ti") ||
                t.includes("suggestions for you")
            );
        };

        const rows = [
            ...dialog.querySelectorAll("div, li")
        ];

        const followers = [];
        const seen = new Set();
        let reachedSuggestions = false;

        for (const row of rows) {
            const rowText = norm(row.innerText || row.textContent || "");

            if (!rowText) continue;

            if (isSuggestionsText(rowText)) {
                reachedSuggestions = true;
                break;
            }

            const anchors = [...row.querySelectorAll('a[href^="/"]')];

            for (const a of anchors) {
                const hrefRaw = a.getAttribute("href") || "";
                const href = new URL(hrefRaw, location.origin).href;

                if (!isValidProfileHref(href)) continue;

                const usernameFromHref = new URL(href).pathname
                    .replace(/^\/+/, "")
                    .replace(/\/+$/, "")
                    .trim();

                if (!usernameFromHref) continue;

                const text = norm(a.innerText || a.textContent || "");
                const username = usernameFromHref;

                if (seen.has(href)) continue;

                seen.add(href);

                followers.push({
                    username,
                    url: href,
                    text,
                    row_text: rowText.slice(0, 300)
                });
            }
        }

        return {
            ok: true,
            reason: reachedSuggestions ? "stopped-before-suggestions" : "no-suggestions-found",
            followers,
            count: followers.length
        };
    })();
    """