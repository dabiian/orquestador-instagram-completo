from typing import Any, Dict, Optional, Tuple
import json
from app.utils.logger import get_logger
from app.utils.image import _download_image_as_data_url
from selenium.webdriver.common.by import By
import re
from app.config.locators.instagram_post_context_locators import (
    InstagramPostContextLocators,
)

class InstagramPostMediaService:
    """
    Service responsible for:
    - waiting until the current post media is present in the DOM
    - detecting the real main image of the current post
    - debugging visible images from the current post
    - analyzing the current image through ai_api
    """

    def __init__(self, browser, ai_api, logger=None):
        self.browser = browser
        self.ai_api = ai_api
        self.log = logger or get_logger(self.__class__.__name__)

    def _execute_script_safe(self, script: str, *args):
        if hasattr(self.browser, "execute_script"):
            return self.browser.execute_script(script, *args)

        if hasattr(self.browser, "driver"):
            return self.browser.driver.execute_script(script, *args)

        raise AttributeError(
            f"Browser wrapper ({self.browser.__class__.__name__}) "
            f"does not expose execute_script or driver"
        )

    def wait_for_current_post_media(
        self,
        max_attempts: int = 8,
        sleep_seconds: int = 1,
    ) -> bool:
        """
        Wait until visible media for the current post appears in the DOM.
        """
        try:
            script = """
            return (() => {
                const media = document.querySelector("div._aagu._aato img");
                if (media) return true;

                const anyCandidate = [...document.querySelectorAll("img")].some(img => {
                    const src = (img.currentSrc || img.getAttribute("src") || "").trim();
                    const rect = img.getBoundingClientRect();
                    return (
                        src &&
                        /instagram|fbcdn/i.test(src) &&
                        rect.width >= 80 &&
                        rect.height >= 80
                    );
                });

                return anyCandidate;
            })();
            """

            for attempt in range(max_attempts):
                ok = self._execute_script_safe(script)
                if ok:
                    self.log.info(
                        "Post media detected on attempt %s",
                        attempt + 1,
                    )
                    return True

                self.log.warning(
                    "Attempt %s: current post media is not visible yet.",
                    attempt + 1,
                )
                self.browser.time_sleep(sleep_seconds)

            self.log.warning(
                "Current post media did not appear after multiple attempts."
            )
            return False

        except Exception as e:
            self.log.warning("Error while waiting for current post media: %s", str(e))
            return False

    def get_first_current_post_image_url_js(self) -> Tuple[bool, Optional[str]]:
        """
        Get the main image URL from the current post.

        Rules:
        - does not rely on <article>
        - excludes profile-like images
        - ranks candidates by size/context
        """
        try:
            script = """
            return (() => {
                const text = (value) => (value || "").trim();

                const isProfileLike = (alt, src) => {
                    const altLc = (alt || "").toLowerCase();
                    const srcLc = (src || "").toLowerCase();

                    return (
                        /profile photo|profile picture|foto del perfil/.test(altLc) ||
                        /anonymous_profile_pic/.test(srcLc) ||
                        /t51\\.2885-19/.test(srcLc) ||
                        /\\/s150x150\\b/.test(srcLc)
                    );
                };

                const scoreCandidate = (img) => {
                    const rect = img.getBoundingClientRect();
                    const alt = text(img.getAttribute("alt"));
                    const src = text(img.currentSrc || img.getAttribute("src"));

                    if (!src) return null;
                    if (!/instagram|fbcdn/i.test(src)) return null;
                    if (isProfileLike(alt, src)) return null;

                    const inMediaContainer = !!img.closest("div._aagu._aato");
                    const inListItem = !!img.closest("li");
                    const naturalWidth = img.naturalWidth || 0;
                    const naturalHeight = img.naturalHeight || 0;
                    const rectWidth = rect.width || 0;
                    const rectHeight = rect.height || 0;

                    let score = 0;

                    if (inMediaContainer) score += 120;
                    if (inListItem) score += 40;
                    if (rectWidth >= 120 && rectHeight >= 120) score += 40;
                    if (naturalWidth >= 300 || naturalHeight >= 300) score += 40;
                    if (/photo by|post|publicación/i.test((alt || "").toLowerCase())) score += 15;
                    if (/t51\\.75761-15|t51\\.82787-15|t51\\.2885-15/.test(src.toLowerCase())) score += 60;
                    if (/\\.webp|\\.jpg|\\.jpeg/.test(src.toLowerCase())) score += 10;
                    if (/\\.png/.test(src.toLowerCase())) score -= 15;

                    return {
                        src,
                        alt,
                        score,
                        inMediaContainer,
                        inListItem,
                        rectWidth,
                        rectHeight,
                        naturalWidth,
                        naturalHeight
                    };
                };

                const selectors = [
                    "div._aagu._aato img",
                    "img"
                ];

                const seen = new Set();
                const candidates = [];

                for (const selector of selectors) {
                    const images = [...document.querySelectorAll(selector)];

                    for (const img of images) {
                        const ranked = scoreCandidate(img);
                        if (!ranked || !ranked.src) continue;
                        if (seen.has(ranked.src)) continue;

                        seen.add(ranked.src);
                        candidates.push(ranked);
                    }
                }

                if (!candidates.length) {
                    return null;
                }

                candidates.sort((a, b) => b.score - a.score);
                return candidates[0].src || null;
            })();
            """

            for attempt in range(8):
                image_url = self._execute_script_safe(script)

                if image_url:
                    image_url = str(image_url).strip()
                    if image_url:
                        self.log.info(
                            "Image URL detected by JS on attempt %s: %s",
                            attempt + 1,
                            image_url,
                        )
                        return True, image_url

                self.log.warning(
                    "Attempt %s: main post image was not found yet.",
                    attempt + 1,
                )
                self.browser.time_sleep(1)

            self.log.warning(
                "JS could not detect a valid main post image after multiple attempts."
            )
            return False, None

        except Exception as e:
            self.log.warning("Error while getting image URL via JS: %s", str(e))
            return False, None

    def debug_current_post_image_js(self) -> Optional[Dict[str, Any]]:
        """
        Unified debug helper for the current post image state.
        """
        try:
            script = """
            return (() => {
                const text = (value) => (value || "").trim();

                const article = document.querySelector("article");

                const mediaImages = [...document.querySelectorAll("div._aagu._aato img")].map((img, i) => {
                    const rect = img.getBoundingClientRect();
                    return {
                        i,
                        alt: text(img.getAttribute("alt")),
                        src: text(img.currentSrc || img.getAttribute("src")),
                        rectWidth: rect.width || 0,
                        rectHeight: rect.height || 0,
                        naturalWidth: img.naturalWidth || 0,
                        naturalHeight: img.naturalHeight || 0,
                        inMediaContainer: true
                    };
                });

                const articleImages = article
                    ? [...article.querySelectorAll("img")].map((img, i) => {
                        const rect = img.getBoundingClientRect();
                        return {
                            i,
                            alt: text(img.getAttribute("alt")),
                            src: text(img.currentSrc || img.getAttribute("src")),
                            rectWidth: rect.width || 0,
                            rectHeight: rect.height || 0,
                            naturalWidth: img.naturalWidth || 0,
                            naturalHeight: img.naturalHeight || 0
                        };
                    })
                    : [];

                const allImages = [...document.querySelectorAll("img")].map((img, i) => {
                    const rect = img.getBoundingClientRect();
                    return {
                        i,
                        alt: text(img.getAttribute("alt")),
                        src: text(img.currentSrc || img.getAttribute("src")),
                        inMediaContainer: !!img.closest("div._aagu._aato"),
                        rectWidth: rect.width || 0,
                        rectHeight: rect.height || 0,
                        naturalWidth: img.naturalWidth || 0,
                        naturalHeight: img.naturalHeight || 0
                    };
                });

                return {
                    article_exists: !!article,
                    media_images_count: mediaImages.length,
                    article_images_count: articleImages.length,
                    all_images_count: allImages.length,
                    media_images: mediaImages.slice(0, 10),
                    article_images: articleImages.slice(0, 10),
                    all_images: allImages.slice(0, 20)
                };
            })();
            """

            debug_data = self._execute_script_safe(script)
            self.log.info("Current post image debug: %s", debug_data)
            return debug_data

        except Exception as e:
            self.log.warning("Error while debugging current post image: %s", str(e))
            return None

    def analyze_current_post_image(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Full flow:
        1) wait for media
        2) get main image URL
        3) download as base64/data-url
        4) send to AI for visual analysis
        5) return (ok, image_url, description)
        """
        try:
            self.wait_for_current_post_media()

            ok_image, image_url = self.get_first_current_post_image_url_js()

            if not ok_image or not image_url:
                self.debug_current_post_image_js()
                self.log.warning(
                    "No valid image URL was found for the current post."
                )
                return False, None, None

            ok_base64, image_base64 = _download_image_as_data_url(image_url)
            if not ok_base64 or not image_base64:
                self.log.warning(
                    "Could not convert current post image to base64."
                )
                return False, image_url, None

            prompt = (
                "Describe only what is actually visible in this Instagram image. "
                "Be brief, clear, and natural. "
                "Do not invent details. "
                "Mention people, objects, setting, actions, visible text, and visual tone if relevant."
            )

            ok_description, response = self.ai_api.analize_image(
                prompt=prompt,
                image_base64=image_base64,
            )

            if not ok_description or not response:
                self.log.warning("AI did not return an image description.")
                return False, image_url, None

            description = str(response).strip()

            if not description:
                self.log.warning("Visual description came back empty.")
                return False, image_url, None

            self.log.info("Visual description obtained successfully.")
            return True, image_url, description

        except Exception as e:
            self.log.warning("Error while analyzing current post image: %s", str(e))
            return False, None, None
            
    def _extract_first_json_object(self, raw_text: str) -> Optional[dict]:
        try:
            if not raw_text:
                return None

            cleaned = str(raw_text).strip()
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

            start = cleaned.find("{")
            end = cleaned.rfind("}")

            if start == -1 or end == -1 or end <= start:
                return None

            json_str = cleaned[start:end + 1]
            return json.loads(json_str)

        except Exception as e:
            self.log.warning("No se pudo parsear JSON de la IA: %r | raw=%r", e, raw_text)
            return None


    def _get_current_post_media_info(self) -> dict:
        """
        Detecta el media principal del post actual.
        Si encuentra video visible, devuelve media_type='video'.
        Si encuentra imagen visible, devuelve media_type='image' + image_url.
        """
        try:
            script = """
            const isVisible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return (
                    style &&
                    style.display !== "none" &&
                    style.visibility !== "hidden" &&
                    rect.width > 40 &&
                    rect.height > 40
                );
            };

            const clean = (v) => String(v || "").trim();

            const article = document.querySelector("article") || document;

            const visibleVideos = [...article.querySelectorAll("video")].filter(isVisible);
            if (visibleVideos.length > 0) {
                const video = visibleVideos[0];
                return {
                    ok: true,
                    media_type: "video",
                    image_url: "",
                    video_url: clean(video.currentSrc || video.src || ""),
                    source: "visible-video"
                };
            }

            const visibleImages = [...article.querySelectorAll("img")]
                .filter(isVisible)
                .map((img) => {
                    const src = clean(img.currentSrc || img.src || "");
                    const width = Number(img.naturalWidth || img.width || 0);
                    const height = Number(img.naturalHeight || img.height || 0);
                    const area = width * height;
                    return {
                        src,
                        width,
                        height,
                        area,
                        alt: clean(img.getAttribute("alt") || "")
                    };
                })
                .filter((img) => img.src && !img.src.startsWith("data:"))
                .sort((a, b) => b.area - a.area);

            if (visibleImages.length > 0) {
                const best = visibleImages[0];
                return {
                    ok: true,
                    media_type: "image",
                    image_url: best.src,
                    video_url: "",
                    width: best.width,
                    height: best.height,
                    alt: best.alt,
                    source: "largest-visible-image"
                };
            }

            const ogImage =
                clean(document.querySelector('meta[property="og:image"]')?.content || "") ||
                clean(document.querySelector('meta[name="twitter:image"]')?.content || "");

            if (ogImage) {
                return {
                    ok: true,
                    media_type: "image",
                    image_url: ogImage,
                    video_url: "",
                    source: "meta-image"
                };
            }

            return {
                ok: false,
                media_type: "unknown",
                image_url: "",
                video_url: "",
                source: "not-found"
            };
            """

            result = self.browser.driver.execute_script(script)

            if not isinstance(result, dict):
                return {
                    "ok": False,
                    "media_type": "unknown",
                    "image_url": "",
                    "video_url": "",
                    "source": "invalid-js-result",
                }

            return result

        except Exception as e:
            self.log.warning("Error obteniendo media del post actual: %r", e)
            return {
                "ok": False,
                "media_type": "unknown",
                "image_url": "",
                "video_url": "",
                "source": "exception",
            }


    def _build_followback_image_validation_prompt(self) -> str:
        return """
    Eres un clasificador estricto de imágenes de Instagram.

    OBJETIVO:
    Determinar si la IMAGEN del post parece ser de tipo "sígueme y te sigo" / "followback" / "follow for follow" / "f4f" / "follow x follow" / "devuelvo follow" / "mutuals" / "gana seguidores".

    REGLAS:
    - Analiza SOLO la imagen del post.
    - NO te bases en comentarios.
    - NO inventes contexto.
    - Si la imagen no muestra señales claras de followback, responde false.
    - Si es una imagen genérica, selfie, meme, paisaje, producto, flyer normal o algo ambiguo, responde false.
    - Solo responde true si hay señales visuales o textuales claras de followback / intercambio de follows / crecer seguidores / mutuals.

    Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta:
    {"is_followback_image": true, "confidence": 0.93, "reason": "texto breve"}
    o
    {"is_followback_image": false, "confidence": 0.12, "reason": "texto breve"}
    """.strip()


    def validate_current_post_followback_image(self) -> dict:
        """
        Devuelve:
        {
            "checked": bool,
            "skipped": bool,
            "is_followback_image": bool,
            "confidence": float,
            "reason": str,
            "media_type": str,
            "image_url": str,
        }

        Regla:
        - Si es video, NO invalida ni valida el post; se omite y manda comentarios.
        """
        media_info = self._get_current_post_media_info()
        media_type = (media_info.get("media_type") or "").strip().lower()
        image_url = (media_info.get("image_url") or "").strip()

        if media_type == "video":
            self.log.info("Post actual es video. Se omite validación por imagen.")
            return {
                "checked": False,
                "skipped": True,
                "is_followback_image": False,
                "confidence": 0.0,
                "reason": "video-post",
                "media_type": "video",
                "image_url": "",
            }

        if media_type != "image" or not image_url:
            self.log.warning("No se pudo obtener imagen válida del post actual.")
            return {
                "checked": False,
                "skipped": True,
                "is_followback_image": False,
                "confidence": 0.0,
                "reason": "image-not-found",
                "media_type": media_type or "unknown",
                "image_url": "",
            }

        ok_base64, image_base64 = _download_image_as_data_url(image_url)
        if not ok_base64 or not image_base64:
            self.log.warning("No se pudo convertir la imagen del post a base64.")
            return {
                "checked": False,
                "skipped": True,
                "is_followback_image": False,
                "confidence": 0.0,
                "reason": "image-base64-failed",
                "media_type": "image",
                "image_url": image_url,
            }

        ok_ai, result = self.ai_api.analyze_followback_image(
            image_base64=image_base64,
        )

        if not ok_ai or not isinstance(result, dict):
            self.log.warning("La IA no pudo clasificar la imagen followback. result=%r", result)
            return {
                "checked": False,
                "skipped": True,
                "is_followback_image": False,
                "confidence": 0.0,
                "reason": (
                    result.get("error")
                    if isinstance(result, dict)
                    else "ai-error"
                ),
                "media_type": "image",
                "image_url": image_url,
            }

        is_followback_image = bool(result.get("is_followback_image", False))

        try:
            confidence = float(result.get("confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0

        reason = str(result.get("reason") or "").strip()

        self.log.info(
            "Validación IA imagen | is_followback_image=%s | confidence=%.2f | reason=%s | image_url=%s",
            is_followback_image,
            confidence,
            reason,
            image_url,
        )

        return {
            "checked": True,
            "skipped": False,
            "is_followback_image": is_followback_image,
            "confidence": confidence,
            "reason": reason,
            "media_type": "image",
            "image_url": image_url,
        }
    
    def get_current_post_author_username(self) -> tuple[bool, str]:
        try:
            elements = self.browser.driver.find_elements(
                By.XPATH,
                InstagramPostContextLocators.POST_AUTHOR_USERNAME,
            )
            if not elements:
                return False, ""

            el = elements[0]
            username = (el.text or "").strip()

            if not username:
                href = (el.get_attribute("href") or "").strip()
                if href:
                    username = href.rstrip("/").split("/")[-1].strip()

            if not username:
                return False, ""

            return True, username

        except Exception as e:
            self.log.warning("Error obteniendo username del autor: %s", str(e))
            return False, ""
        

    def get_current_post_caption(self) -> tuple[bool, str]:
        try:
            elements = self.browser.driver.find_elements(
                By.XPATH,
                InstagramPostContextLocators.POST_CAPTION,
            )

            if not elements:
                elements = self.browser.driver.find_elements(
                    By.XPATH,
                    InstagramPostContextLocators.POST_CAPTION_FALLBACK,
                )


            if not elements:
                return False, ""

            caption = (elements[0].text or "").strip()

            if not caption:
                return False, ""

            return True, caption

        except Exception as e:
            self.log.warning("Error obteniendo caption del post: %s", str(e))
            return False, ""
        
    def get_current_post_context(self) -> dict:
        ok_author, author_username = self.get_current_post_author_username()
        ok_caption, caption = self.get_current_post_caption()

        print(f"[current-post-context] {author_username} - {caption}")

        return {
            "author_username": author_username if ok_author else "",
            "caption": caption if ok_caption else "",
        }
    


    def get_current_profile_description_context(self) -> dict:
        """
        Saca solo:
        - category (ej: Producto/servicio)
        - profile_description (la bio visible del perfil)
        Ignora links.
        """
        try:
            def clean_text(text: str) -> str:
                text = str(text or "").strip()
                text = re.sub(r"\s+\n", "\n", text)
                text = re.sub(r"\n\s+", "\n", text)
                text = re.sub(r"[ \t]+", " ", text).strip()
                return text

            def first_visible_text(xpaths: list[str]) -> str:
                for xpath in xpaths:
                    try:
                        elements = self.browser.driver.find_elements(By.XPATH, xpath)
                        for el in elements:
                            try:
                                if not el.is_displayed():
                                    continue
                                text = clean_text(el.text)
                                if text:
                                    return text
                            except Exception:
                                continue
                    except Exception:
                        continue
                return ""

            category_text = first_visible_text([
                "//div[normalize-space()='Producto/servicio']",
                "//div[normalize-space()='Product/service']",
                "//span[normalize-space()='Producto/servicio']",
                "//span[normalize-space()='Product/service']",
            ])

            profile_description = first_visible_text([
                "//span[@dir='auto'][.//br]",
                "//header//span[@dir='auto'][.//br]",
                "//header//div[@role='button']//span[@dir='auto'][.//br]",
            ])

            context = {
                "profile_category": category_text,
                "profile_description": profile_description,
            }

            print(f"[owner-profile-description-context] {context}")
            return context

        except Exception as e:
            self.log.warning("Error obteniendo descripción del perfil owner: %r", e)
            return {
                "profile_category": "",
                "profile_description": "",
            }

    def current_post_has_video(self) -> bool:
        """
        Detecta si la publicación actual contiene un video visible.
        """
        try:
            xpaths = [
                "//article//video",
                "//div[@role='dialog']//video",
                "//video",
                "//*[@aria-label='Video player']",
                "//*[@aria-label='Reproducir']",
            ]

            for xpath in xpaths:
                try:
                    elements = self.browser.driver.find_elements(By.XPATH, xpath)
                    for el in elements:
                        try:
                            if el.is_displayed():
                                print(f"[post-media] video detectado con xpath: {xpath}")
                                return True
                        except Exception:
                            continue
                except Exception:
                    continue

            return False

        except Exception as e:
            self.log.warning("Error detectando si el post actual es video: %r", e)
            return False
        

    def get_current_post_context_runtime_generic(
        self,
        max_attempts: int = 8,
        sleep_seconds: int = 1,
    ) -> dict:
        """
        Extrae username + caption del post/reel actual de forma genérica,
        sin depender de h1, _a9zr ni username quemado.

        NO toca los métodos viejos.
        """
        try:
            script = r"""
            return (() => {
                const clean = (v) => String(v || "").replace(/\s+/g, " ").trim();

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

                const isProfileHref = (href) => {
                    const h = clean(href);
                    if (!h.startsWith("/")) return false;

                    const blocked = [
                        "/reel/",
                        "/p/",
                        "/tv/",
                        "/explore/",
                        "/stories/",
                        "/direct/",
                        "/accounts/",
                        "/reels/audio/",
                        "/about/",
                    ];

                    if (h === "/") return false;
                    if (blocked.some(x => h.includes(x))) return false;

                    return true;
                };

                const isTimeLike = (text) => {
                    const t = clean(text).toLowerCase();
                    return (
                        /^\d+\s*(sem|min|h|d)$/.test(t) ||
                        /^ahora$/.test(t) ||
                        /^\d+\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)$/.test(t)
                    );
                };

                const isBlockedText = (text) => {
                    const t = clean(text).toLowerCase();
                    const blocked = new Set([
                        "",
                        "instagram",
                        "inicio",
                        "reels",
                        "mensajes",
                        "búsqueda",
                        "busqueda",
                        "perfil",
                        "audio original",
                        "seguir",
                        "siguiendo",
                        "ver traducción",
                        "ver traduccion",
                        "traducción",
                        "traduccion",
                        "responder",
                        "publicar",
                        "emoji",
                        "me gusta",
                        "comentar",
                        "guardar",
                        "más opciones",
                        "mas opciones",
                        "like",
                        "reply",
                        "share",
                        "save"
                    ]);

                    if (blocked.has(t)) return true;
                    if (isTimeLike(t)) return true;
                    return false;
                };

                const getUsernameFromAnchor = (a) => {
                    if (!a) return "";

                    const text = clean(a.innerText || a.textContent || "");
                    if (text && !isBlockedText(text) && text.toLowerCase() !== "instagram") {
                        return text;
                    }

                    const href = clean(a.getAttribute("href") || "");
                    if (isProfileHref(href)) {
                        return clean(href.replace(/^\/+/, "").replace(/\/+$/, ""));
                    }

                    return "";
                };

                const roots = [
                    ...document.querySelectorAll("div[role='dialog']"),
                    ...document.querySelectorAll("article"),
                    ...document.querySelectorAll("main"),
                    document
                ];

                const candidates = [];

                for (const root of roots) {
                    const anchors = [...root.querySelectorAll("a[href^='/']")]
                        .filter(isVisible)
                        .filter(a => isProfileHref(clean(a.getAttribute("href") || "")));

                    for (const anchor of anchors) {
                        const username = getUsernameFromAnchor(anchor);
                        if (!username) continue;

                        let box = anchor;
                        for (let level = 0; level < 8 && box; level++) {
                            box = box.parentElement;
                            if (!box) break;

                            const texts = [
                                ...box.querySelectorAll("h1, h2, span[dir='auto'], span, div[dir='auto']")
                            ]
                            .filter(isVisible)
                            .map(el => clean(el.innerText || el.textContent || ""))
                            .filter(Boolean);

                            const captionCandidates = texts.filter(text => {
                                const lc = text.toLowerCase();
                                if (!text) return false;
                                if (lc === username.toLowerCase()) return false;
                                if (isBlockedText(text)) return false;
                                if (text.length < 8) return false;
                                return true;
                            });

                            const caption =
                                captionCandidates.find(t => t.includes("#")) ||
                                captionCandidates.sort((a, b) => b.length - a.length)[0] ||
                                "";

                            let score = 0;

                            if (caption) score += 100;
                            if (caption.length >= 20) score += 30;
                            if (caption.includes("#")) score += 20;

                            const boxText = clean(box.innerText || box.textContent || "").toLowerCase();

                            if (/seguir|siguiendo/.test(boxText)) score += 10;
                            if (/ver traducción|ver traduccion/.test(boxText)) score += 15;
                            if (/audio original/.test(boxText)) score += 10;
                            if (/más opciones|mas opciones/.test(boxText)) score += 5;
                            if (/responder/.test(boxText)) score -= 10;

                            const hasTime = [...box.querySelectorAll("time")]
                                .some(el => isVisible(el));
                            if (hasTime) score += 15;

                            candidates.push({
                                username,
                                caption,
                                score,
                                level,
                                href: clean(anchor.getAttribute("href") || ""),
                                preview: boxText.slice(0, 300)
                            });
                        }
                    }
                }

                candidates.sort((a, b) => b.score - a.score);

                if (!candidates.length) {
                    return {
                        ok: false,
                        source: "no-candidates",
                        author_username: "",
                        caption: "",
                        debug_top: []
                    };
                }

                const best = candidates[0];

                return {
                    ok: !!(best.username || best.caption),
                    source: "scored-profile-block",
                    author_username: best.username || "",
                    caption: best.caption || "",
                    debug_top: candidates.slice(0, 5)
                };
            })();
            """

            for attempt in range(max_attempts):
                result = self._execute_script_safe(script)

                if isinstance(result, dict):
                    username = str(result.get("author_username") or "").strip()
                    caption = str(result.get("caption") or "").strip()
                    source = str(result.get("source") or "").strip()

                    self.log.info(
                        "context_runtime_generic | intento=%s/%s | source=%s | username=%r | caption_len=%s",
                        attempt + 1,
                        max_attempts,
                        source,
                        username,
                        len(caption),
                    )

                    if username or caption:
                        print(f"[current-post-context-runtime-generic] ({source}) {username} - {caption}")
                        return {
                            "author_username": username,
                            "caption": caption,
                        }

                self.browser.time_sleep(sleep_seconds)

            print("[current-post-context-runtime-generic]  - ")
            return {
                "author_username": "",
                "caption": "",
            }

        except Exception as e:
            self.log.warning("Error obteniendo context runtime generic: %s", str(e))
            return {
                "author_username": "",
                "caption": "",
            }

    def _clean_runtime_caption_text(self, caption: str, author_username: str = "") -> str:
        try:
            text = str(caption or "").strip()
            author_username = str(author_username or "").strip()

            if not text:
                return ""

            text = re.sub(r"\s+", " ", text).strip()

            if author_username:
                pattern_username = rf"^\s*@?{re.escape(author_username)}\s*"
                text = re.sub(pattern_username, "", text, flags=re.IGNORECASE).strip()

            text = re.sub(r"^(ahora)\s*", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"^\d+\s*(sem|min|h|d)\s*", "", text, flags=re.IGNORECASE).strip()

            text = re.sub(
                r"^\d{1,2}\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(\s+de\s+\d{4})?\s*",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()

            text = re.sub(r"^(ver traducción|ver traduccion)\s*", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"^(audio original)\s*", "", text, flags=re.IGNORECASE).strip()

            if author_username:
                text = re.sub(rf"^\s*@?{re.escape(author_username)}\s*", "", text, flags=re.IGNORECASE).strip()

            return text.strip()

        except Exception as e:
            self.log.warning("Error limpiando caption runtime: %s", str(e))
            return str(caption or "").strip()