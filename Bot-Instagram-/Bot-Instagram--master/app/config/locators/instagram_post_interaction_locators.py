class InstagramPostInteractionLocators:
    """
    Locators y scripts centralizados para interactuar con un post abierto:
    - like
    - comentar
    - publicar comentario
    - repost/share
    - lectura/escritura de cajas de comentario/reply
    """

    # =========================================================
    # COMMENT BOX / PUBLISH
    # =========================================================

    POST_COMMENT_BOX = (
        "//textarea"
        " | //form//textarea"
        " | //article//textarea"
        " | //div[@role='textbox' and @contenteditable='true']"
        " | //form//div[@role='textbox' and @contenteditable='true']"
        " | //article//div[@role='textbox' and @contenteditable='true']"
    )

    POST_COMMENT_PUBLISH = (
        "//*[@role='button' and (normalize-space()='Publicar' or normalize-space()='Post')]"
        " | //button[normalize-space()='Publicar' or normalize-space()='Post']"
        " | //button[.//*[normalize-space()='Publicar' or normalize-space()='Post']]"
        " | //*[@role='button' and (normalize-space()='Comentar' or normalize-space()='Comment')]"
        " | //button[normalize-space()='Comentar' or normalize-space()='Comment']"
    )

    POST_COMMENT_PUBLISH_ENABLED = (
        "//*[@role='button' and not(@aria-disabled='true') "
        "and (normalize-space()='Publicar' or normalize-space()='Post')]"
        " | //button[not(@disabled) and (normalize-space()='Publicar' or normalize-space()='Post')]"
        " | //button[not(@disabled) and .//*[normalize-space()='Publicar' or normalize-space()='Post']]"
        " | //*[@role='button' and not(@aria-disabled='true') "
        "and (normalize-space()='Comentar' or normalize-space()='Comment')]"
        " | //button[not(@disabled) and (normalize-space()='Comentar' or normalize-space()='Comment')]"
    )

    # =========================================================
    # SMALL JS HELPERS
    # =========================================================

    CLICK_ELEMENT_SCRIPT = "arguments[0].click();"

    SCROLL_INTO_VIEW_CENTER_SCRIPT = (
        "arguments[0].scrollIntoView({block: 'center', inline: 'center'});"
    )

    READ_INPUT_TEXT_SCRIPT = """
    const el = arguments[0];

    if (!el) return '';

    const tag = (el.tagName || '').toLowerCase();

    if (tag === 'textarea' || tag === 'input') {
        return (el.value || '').trim();
    }

    return (el.innerText || el.textContent || '').trim();
    """

    # =========================================================
    # LIKE STATE / LIKE CLICK
    # =========================================================

    GET_POST_LIKE_STATE_SCRIPT = """
    const sections = [...document.querySelectorAll("section")];

    for (const section of sections) {
        const hasComment = !!section.querySelector(
            'svg[aria-label="Comentar"], svg[aria-label="Comment"]'
        );

        const hasSave = !!section.querySelector(
            'svg[aria-label="Guardar"], svg[aria-label="Save"], svg[aria-label="Save to collection"]'
        );

        if (!hasComment || !hasSave) continue;

        const likedSvg = section.querySelector(
            'span.x1qfufaz div[role="button"] svg[aria-label="Ya no me gusta"], ' +
            'span.x1qfufaz div[role="button"] svg[aria-label="Unlike"]'
        );

        if (likedSvg) {
            return "liked";
        }

        const notLikedSvg = section.querySelector(
            'span.x1qfufaz div[role="button"] svg[aria-label="Me gusta"], ' +
            'span.x1qfufaz div[role="button"] svg[aria-label="Like"]'
        );

        if (notLikedSvg) {
            return "not_liked";
        }
    }

    return "unknown";
    """

    CLICK_POST_LIKE_SCRIPT = """
    const sections = [...document.querySelectorAll("section")];

    for (const section of sections) {
        const hasComment = !!section.querySelector(
            'svg[aria-label="Comentar"], svg[aria-label="Comment"]'
        );

        const hasSave = !!section.querySelector(
            'svg[aria-label="Guardar"], svg[aria-label="Save"], svg[aria-label="Save to collection"]'
        );

        if (!hasComment || !hasSave) continue;

        const notLikedSvg = section.querySelector(
            'span.x1qfufaz div[role="button"] svg[aria-label="Me gusta"], ' +
            'span.x1qfufaz div[role="button"] svg[aria-label="Like"]'
        );

        if (!notLikedSvg) continue;

        const button = notLikedSvg.closest('div[role="button"], button');

        if (!button) continue;

        button.scrollIntoView({ block: "center", inline: "center" });

        try {
            button.click();
            return true;
        } catch (e) {
            try {
                ['mousedown', 'mouseup', 'click'].forEach(type => {
                    button.dispatchEvent(new MouseEvent(type, {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }));
                });
                return true;
            } catch (e2) {}
        }
    }

    return false;
    """

    # =========================================================
    # WRITE COMMENT / REPLY
    # =========================================================

    WRITE_TEXT_TO_COMMENT_BOX_SCRIPT = """
    const el = arguments[0];
    const text = arguments[1];

    if (!el) return null;

    el.focus();

    const tagName = el.tagName || '';
    const isTextarea = tagName === 'TEXTAREA';
    const isInput = tagName === 'INPUT';
    const isContentEditable = el.isContentEditable || el.getAttribute('contenteditable') === 'true';

    try {
        if (isTextarea || isInput) {
            const proto = isTextarea
                ? window.HTMLTextAreaElement.prototype
                : window.HTMLInputElement.prototype;

            const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
            const setter = descriptor && descriptor.set;

            if (setter) {
                setter.call(el, text);
            } else {
                el.value = text;
            }
        } else if (isContentEditable) {
            el.innerHTML = '';
            el.textContent = text;
        } else {
            return null;
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

        if (isTextarea || isInput) {
            return el.value || '';
        }

        if (isContentEditable) {
            return el.textContent || '';
        }

        return null;
    } catch (e) {
        return null;
    }
    """

    TYPE_INTO_COMMENT_BOX_VISIBLE_SCRIPT = """
    const el = arguments[0];
    const text = arguments[1];

    if (!el) return false;

    el.focus();

    const tagName = el.tagName || '';
    const isTextarea = tagName === 'TEXTAREA';
    const isInput = tagName === 'INPUT';
    const isContentEditable = el.isContentEditable || el.getAttribute('contenteditable') === 'true';

    try {
        if (isTextarea || isInput) {
            const proto = isTextarea
                ? window.HTMLTextAreaElement.prototype
                : window.HTMLInputElement.prototype;

            const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
            const setter = descriptor && descriptor.set;

            if (setter) {
                setter.call(el, text);
            } else {
                el.value = text;
            }
        } else if (isContentEditable) {
            el.innerHTML = '';
            el.textContent = text;
        } else {
            return "";
        }

        el.dispatchEvent(new InputEvent('input', {
            bubbles: true,
            cancelable: true,
            data: text,
            inputType: 'insertText'
        }));

        el.dispatchEvent(new Event('change', { bubbles: true }));

        return (el.value || el.innerText || el.textContent || '').trim();
    } catch (e) {
        return "";
    }
    """

    # =========================================================
    # REPOST / SHARE CURRENT POST
    # =========================================================

    SHARE_CURRENT_POST_SCRIPT = """
    return (() => {
        const isVisible = (el) => {
            if (!el) return false;

            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();

            return (
                style &&
                style.display !== "none" &&
                style.visibility !== "hidden" &&
                rect.width > 0 &&
                rect.height > 0
            );
        };

        const sections = [...document.querySelectorAll("section")];

        for (const section of sections) {
            if (!isVisible(section)) continue;

            const hasComment = !!section.querySelector(
                'svg[aria-label="Comentar"], svg[aria-label="Comment"]'
            );

            const hasSave = !!section.querySelector(
                'svg[aria-label="Guardar"], svg[aria-label="Save"], svg[aria-label="Save to collection"]'
            );

            if (!hasComment || !hasSave) continue;

            const repostSvg = section.querySelector(
                'svg[aria-label="Republicar"], svg[aria-label="Repost"]'
            );

            if (!repostSvg) continue;

            const button = repostSvg.closest('div[role="button"], button');

            if (!button || !isVisible(button)) continue;

            button.scrollIntoView({ block: "center", inline: "center" });

            try {
                button.click();
                return true;
            } catch (e) {
                try {
                    ['mousedown', 'mouseup', 'click'].forEach(type => {
                        button.dispatchEvent(new MouseEvent(type, {
                            bubbles: true,
                            cancelable: true,
                            view: window
                        }));
                    });
                    return true;
                } catch (e2) {}
            }
        }

        return false;
    })();
    """

    CLICK_PUBLISH_BUTTON_NEAR_COMMENT_BOX_SCRIPT = r"""
    return (() => {
        const commentBox = arguments[0];

        const norm = (txt) => {
            return String(txt || "")
                .replace(/\s+/g, " ")
                .trim();
        };

        const lower = (txt) => norm(txt).toLowerCase();

        const isVisible = (el) => {
            if (!el) return false;

            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();

            return (
                style.display !== "none" &&
                style.visibility !== "hidden" &&
                rect.width > 0 &&
                rect.height > 0
            );
        };

        const isDisabled = (el) => {
            if (!el) return true;

            const ariaDisabled = String(el.getAttribute("aria-disabled") || "").toLowerCase();
            const disabled = !!el.disabled;

            const style = window.getComputedStyle(el);
            const opacity = parseFloat(style.opacity || "1");

            return (
                disabled ||
                ariaDisabled === "true" ||
                opacity < 0.45
            );
        };

        const clickElement = (el) => {
            if (!el) {
                return { ok: false, reason: "no-element" };
            }

            try {
                el.scrollIntoView({ block: "center", inline: "center" });
            } catch (e) {}

            try {
                el.dispatchEvent(new MouseEvent("mouseover", {
                    bubbles: true,
                    cancelable: true,
                    view: window
                }));

                el.dispatchEvent(new MouseEvent("mouseenter", {
                    bubbles: true,
                    cancelable: true,
                    view: window
                }));

                el.dispatchEvent(new MouseEvent("mousedown", {
                    bubbles: true,
                    cancelable: true,
                    view: window
                }));

                el.dispatchEvent(new MouseEvent("mouseup", {
                    bubbles: true,
                    cancelable: true,
                    view: window
                }));

                el.click();

                return {
                    ok: true,
                    reason: "clicked",
                    text: norm(el.innerText || el.textContent || ""),
                    tag: el.tagName,
                    role: el.getAttribute("role") || "",
                    ariaDisabled: el.getAttribute("aria-disabled") || "",
                    disabled: !!el.disabled
                };
            } catch (e) {
                return {
                    ok: false,
                    reason: String(e),
                    text: norm(el.innerText || el.textContent || "")
                };
            }
        };

        if (!commentBox) {
            return { ok: false, reason: "no-comment-box" };
        }

        const allowedLabels = new Set([
            "publicar",
            "post",
            "comentar",
            "comment",
            "responder",
            "reply"
        ]);

        const roots = [];

        const form = commentBox.closest("form");
        if (form) roots.push(form);

        const article = commentBox.closest("article");
        if (article) roots.push(article);

        const dialog = commentBox.closest('div[role="dialog"]');
        if (dialog) roots.push(dialog);

        const main = document.querySelector("main");
        if (main) roots.push(main);

        roots.push(document);

        const seenRoots = new Set();
        const candidates = [];

        for (const root of roots) {
            if (!root || seenRoots.has(root)) continue;
            seenRoots.add(root);

            const nodes = [
                ...root.querySelectorAll("button"),
                ...root.querySelectorAll('div[role="button"]')
            ];

            for (const node of nodes) {
                if (!node || !isVisible(node)) continue;

                const text = lower(node.innerText || node.textContent || "");
                const aria = lower(node.getAttribute("aria-label") || "");

                const labelMatch =
                    allowedLabels.has(text) ||
                    allowedLabels.has(aria) ||
                    [...allowedLabels].some(label => text === label || aria === label);

                if (!labelMatch) continue;

                candidates.push({
                    node,
                    text,
                    aria,
                    disabled: isDisabled(node)
                });
            }

            const enabled = candidates.find(item => !item.disabled);
            if (enabled) {
                return clickElement(enabled.node);
            }
        }

        return {
            ok: false,
            reason: "publish-button-not-found-or-disabled",
            candidates: candidates.slice(0, 10).map(item => ({
                text: item.text,
                aria: item.aria,
                disabled: item.disabled
            }))
        };
    })();
    """