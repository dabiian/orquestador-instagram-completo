class InstagramReplyMonitorLocators:
    """
    Locators/scripts centralizados para monitorear replies en comentarios de prospectos.

    Usado por:
    - InstagramProspectReplyMonitorTask
    """

    # =========================================================
    # DEBUG
    # =========================================================

    DEBUG_REPLY_LI_COUNT_SCRIPT = """
    return document.querySelectorAll('li._a9ye').length;
    """

    DEBUG_REPLY_PERMALINK_COUNT_SCRIPT = """
    return document.querySelectorAll('a[href*="/r/"]').length;
    """

    # =========================================================
    # EXPAND REPLIES
    # =========================================================

    EXPAND_ALL_REPLY_THREADS_XPATH = (
        "//*[(@role='button' or self::button) and "
        "((contains(normalize-space(.), 'Ver las') and contains(normalize-space(.), 'respuestas')) "
        "or (contains(normalize-space(.), 'View') and contains(normalize-space(.), 'repl')))]"
    )

    CLICK_ELEMENT_SCRIPT = "arguments[0].click();"

    EXPAND_REPLY_THREAD_FOR_OUR_COMMENT_SCRIPT = """
    const snippet = (arguments[0] || '').toLowerCase();

    const norm = (txt) => (txt || '').replace(/\\s+/g, ' ').trim().toLowerCase();

    const isReplyExpandBtn = (el) => {
        const txt = norm(el.innerText || el.textContent || '');
        return (
            (txt.includes('ver las') && txt.includes('respuestas')) ||
            (txt.includes('view') && txt.includes('repl'))
        );
    };

    const buttons = [...document.querySelectorAll('[role="button"], button')];

    for (const btn of buttons) {
        if (!isReplyExpandBtn(btn)) continue;

        let node = btn;
        for (let i = 0; i < 10 && node; i++) {
            node = node.parentElement;
            if (!node) break;

            const blockText = norm(node.innerText || node.textContent || '');
            if (blockText.includes(snippet)) {
                btn.scrollIntoView({ block: 'center', inline: 'center' });
                btn.click();
                return true;
            }
        }
    }

    return false;
    """

    # =========================================================
    # EXTRACT REPLIES
    # =========================================================

    EXTRACT_REPLIES_FROM_PROSPECT_SCRIPT = r"""
    return (() => {
        const COMMENT_SNIPPET = arguments[1] || "";
        const PROSPECT_USERNAME = arguments[0] || "";

        const norm = (txt) => (txt || "").replace(/\s+/g, " ").trim();
        const normLower = (txt) => norm(txt).toLowerCase();

        const snippet = normLower(COMMENT_SNIPPET);
        const username = normLower(PROSPECT_USERNAME);

        function visible(el) {
            if (!el) return false;
            const st = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return (
                st.display !== "none" &&
                st.visibility !== "hidden" &&
                r.width > 0 &&
                r.height > 0
            );
        }

        function getButtons(node) {
            if (!node?.querySelectorAll) return [];
            return [...node.querySelectorAll('button, [role="button"]')].filter(visible);
        }

        function isReplyBtnText(txt) {
            const t = normLower(txt);
            return t === "responder" || t === "reply";
        }

        function isExpandRepliesText(txt) {
            const t = normLower(txt);
            return (
                (t.includes("ver las") && t.includes("respuestas")) ||
                (t.includes("view") && t.includes("repl"))
            );
        }

        function isNoiseText(txt) {
            const t = normLower(txt);

            if (!t) return true;

            return [
                username,
                "responder",
                "reply",
                "ver traducción",
                "see translation",
                "me gusta",
                "like",
                "ocultar respuestas",
                "hide replies",
                "seguir",
                "follow"
            ].includes(t) || /^\d+\s*(min|h|d|s|m|sem)$/.test(t);
        }

        function bestTextFrom(node) {
            const spans = [...node.querySelectorAll('span[dir="auto"], span._ap3a, h1, h2, h3')]
                .map(el => norm(el.textContent))
                .filter(Boolean)
                .filter(t => !isNoiseText(t));

            if (!spans.length) return "";

            return spans.sort((a, b) => b.length - a.length)[0];
        }

        const leafCandidates = [
            ...document.querySelectorAll('span[dir="auto"], span._ap3a, h1, h2, h3')
        ];

        const exactLeaf = leafCandidates.find(el => {
            const txt = normLower(el.textContent || "");
            return txt === snippet || txt.includes(snippet);
        });

        if (!exactLeaf) {
            return [];
        }

        let ownRoot = null;
        let node = exactLeaf;

        for (let i = 0; i < 15 && node; i++) {
            const hasCommentPermalink = !!node.querySelector?.('a[href*="/c/"]');
            const hasReplyBtn = getButtons(node).some(
                btn => isReplyBtnText(btn.innerText || btn.textContent || "")
            );

            if (hasCommentPermalink && hasReplyBtn) {
                ownRoot = node;
                break;
            }

            node = node.parentElement;
        }

        if (!ownRoot) {
            return [];
        }

        let expandBtn = getButtons(ownRoot).find(
            btn => isExpandRepliesText(btn.innerText || btn.textContent || "")
        );

        if (!expandBtn) {
            let probe = ownRoot;

            for (let up = 0; up < 6 && probe && !expandBtn; up++) {
                let sib = probe.nextElementSibling;
                let hops = 0;

                while (sib && hops < 10 && !expandBtn) {
                    expandBtn = getButtons(sib).find(
                        btn => isExpandRepliesText(btn.innerText || btn.textContent || "")
                    );

                    sib = sib.nextElementSibling;
                    hops++;
                }

                probe = probe.parentElement;
            }
        }

        if (expandBtn) {
            expandBtn.scrollIntoView({ block: "center", inline: "center" });
            expandBtn.click();
        }

        function collectFollowingContainers(startNode) {
            const roots = [];
            let anchor = startNode;

            for (let up = 0; up < 7 && anchor; up++) {
                let sib = anchor.nextElementSibling;
                let hops = 0;

                while (sib && hops < 12) {
                    roots.push(sib);
                    sib = sib.nextElementSibling;
                    hops++;
                }

                anchor = anchor.parentElement;
            }

            return roots;
        }

        const containers = collectFollowingContainers(ownRoot);

        const out = [];
        const seen = new Set();

        for (const container of containers) {
            const userAnchors = [
                ...container.querySelectorAll(`a[href^="/${username}/"]`)
            ].filter(visible);

            if (!userAnchors.length) continue;

            const replyButtons = getButtons(container).filter(
                btn => isReplyBtnText(btn.innerText || btn.textContent || "")
            );

            if (!replyButtons.length) continue;

            for (const userAnchor of userAnchors) {
                let replyRoot = userAnchor;
                let found = null;

                for (let i = 0; i < 12 && replyRoot; i++) {
                    const hasUser = !!replyRoot.querySelector?.(`a[href^="/${username}/"]`);
                    const hasReplyBtn = getButtons(replyRoot).some(
                        btn => isReplyBtnText(btn.innerText || btn.textContent || "")
                    );
                    const txt = normLower(replyRoot.innerText || replyRoot.textContent || "");

                    if (hasUser && hasReplyBtn && !txt.includes(snippet)) {
                        found = replyRoot;
                        break;
                    }

                    replyRoot = replyRoot.parentElement;
                }

                if (!found) continue;

                const permalinkAnchor =
                    found.querySelector('a[href*="/c/"]') ||
                    found.querySelector('a[href*="/r/"]');

                const permalink = permalinkAnchor?.href || "";
                const text = bestTextFrom(found);

                if (!text) continue;

                const key = `${userAnchor.href}|${permalink}|${text}`;

                if (seen.has(key)) continue;

                seen.add(key);

                out.push({
                    username,
                    text,
                    profile_href: userAnchor.href,
                    permalink,
                    root_text: norm(found.innerText || found.textContent || "").slice(0, 500)
                });
            }
        }

        return out;
    })();
    """

    # =========================================================
    # CLICK REPLY
    # =========================================================

    CLICK_REPLY_ON_COMMENT_SCRIPT = """
    const profileHrefRaw = arguments[0];
    const permalinkRaw = arguments[1];

    const norm = (href) => {
        if (!href) return "";
        return String(href)
            .replace(location.origin, "")
            .trim()
            .replace(/\\/+$/, "") + "/";
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

                const replyBtn = [...current.querySelectorAll('[role="button"], button')].find(btn => {
                    const txt = (btn.innerText || btn.textContent || '')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .toLowerCase();

                    return txt === 'responder' || txt === 'reply';
                });

                if (hasExactPermalink && hasExactUser && replyBtn) {
                    return { root: current, btn: replyBtn };
                }

                current = current.parentElement;
            }
        }

        return null;
    };

    const found = findExactCommentRoot();

    if (!found || !found.btn) {
        return {
            ok: false,
            reason: "reply-button-not-found",
            profileHref,
            permalink
        };
    }

    found.btn.scrollIntoView({ block: "center", inline: "center" });
    found.btn.click();

    return {
        ok: true,
        reason: "clicked",
        profileHref,
        permalink
    };
    """

    # =========================================================
    # CLICK LIKE
    # =========================================================

    CLICK_LIKE_ON_COMMENT_SCRIPT = """
    const profileHrefRaw = arguments[0];
    const permalinkRaw = arguments[1];

    const norm = (href) => {
        if (!href) return "";
        return String(href)
            .replace(location.origin, "")
            .trim()
            .replace(/\\/+$/, "") + "/";
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
        return {
            ok: false,
            reason: "root-not-found",
            profileHref,
            permalink
        };
    }

    const likeBtn =
        root.querySelector('span._a9zu div[role="button"]') ||
        root.querySelector('div[role="button"] svg[aria-label="Me gusta"]')?.closest('div[role="button"]') ||
        root.querySelector('div[role="button"] svg[aria-label="Like"]')?.closest('div[role="button"]') ||
        root.querySelector('div[role="button"] svg[aria-label="Ya no me gusta"]')?.closest('div[role="button"]') ||
        root.querySelector('div[role="button"] svg[aria-label="Unlike"]')?.closest('div[role="button"]');

    if (!likeBtn) {
        return {
            ok: false,
            reason: "like-not-found",
            profileHref,
            permalink
        };
    }

    const isAlreadyLiked =
        !!likeBtn.querySelector('svg[aria-label="Ya no me gusta"]') ||
        !!likeBtn.querySelector('svg[aria-label="Unlike"]') ||
        (
            !!likeBtn.querySelector('title') &&
            ["Ya no me gusta", "Unlike"].includes(
                (likeBtn.querySelector('title')?.textContent || "").trim()
            )
        );

    if (isAlreadyLiked) {
        return {
            ok: true,
            reason: "already-liked",
            profileHref,
            permalink
        };
    }

    likeBtn.scrollIntoView({ block: "center", inline: "center" });
    likeBtn.dispatchEvent(new MouseEvent("mouseover", { bubbles: true, cancelable: true }));
    likeBtn.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true, cancelable: true }));
    likeBtn.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    likeBtn.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
    likeBtn.click();

    return {
        ok: true,
        reason: "clicked",
        profileHref,
        permalink
    };
    """