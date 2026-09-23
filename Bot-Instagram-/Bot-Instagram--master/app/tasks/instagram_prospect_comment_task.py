import random
from datetime import datetime, timezone

from app.core.interfaces import ITask
from app.utils.logger import get_logger

from app.api.prospecting_api import ProspectingAPI
from app.services.instagram_post_media_service import InstagramPostMediaService
from app.services.instagram_post_interaction_service import InstagramPostInteractionService
from app.services.instagram_comment_generation_service import InstagramCommentGenerationService
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService
from app.services.instagram_safety_gate import InstagramSafetyGate


class InstagramProspectCommentTask(ITask):
    """
    Comenta publicaciones de prospectos ya calificadas como relevantes.

    Usa el mismo patrón que la task del owner:
    - InstagramCommentGenerationService
    - InstagramPostInteractionService

    Pero con una categoría distinta para prospectación.
    """

    def __init__(self, browser, data: dict, account_api, ai_api):
        self.browser = browser
        self.data = data or {}
        self.account_api = account_api
        self.ai_api = ai_api
        self.log = get_logger(self.__class__.__name__)

        self.prospecting_api = ProspectingAPI()

        self.post_media_service = InstagramPostMediaService(
            browser=self.browser,
            ai_api=self.ai_api,
            logger=self.log,
        )

        self.post_interaction_service = InstagramPostInteractionService(
            browser=self.browser,
            logger=self.log,
        )

        self.safety_gate = None
        self.comment_generation_service = InstagramCommentGenerationService(
            data=self.data,
            account_api=self.account_api,
            ai_api=self.ai_api,
            post_media_service=self.post_media_service,
            logger=self.log,
        )

    def _sleep_config_delay(self, action: str) -> None:
        campaign_type = getattr(self, "_runtime_campaign_type", None) or InstagramConfigRuntimeService.campaign(
            (self.data.get("campaign") or {}).get("campaign_type")
            or self.data.get("campaign_type")
            or "botanica"
        )
        delay = InstagramConfigRuntimeService.delay(campaign_type, action)
        if not delay:
            return
        try:
            self.browser.time_sleep(random.uniform(float(delay.get("min", 0)), float(delay.get("max", delay.get("min", 0)))))
        except (TypeError, ValueError):
            pass

    def execute(self) -> bool:
        try:
            account_id = self._get_social_media_account_id()
            if not account_id:
                self.log.warning("No se encontró social_media_account.id en ProspectCommentTask")
                return False

            ok_campaign, campaign = self.prospecting_api.get_active_campaign(
                social_media_account_id=account_id,
                platform="instagram",
            )

            self.log.info(
                "[prospecting-comment] get_active_campaign | ok=%s | campaign=%s | account_id=%s",
                ok_campaign,
                campaign,
                account_id,
            )

            if not ok_campaign or not campaign:
                self.log.warning("No se encontró campaña activa para comentar.")
                return False

            campaign_id = campaign["id"]
            campaign_type = InstagramConfigRuntimeService.campaign(
                campaign.get("campaign_type")
                or campaign.get("industry_target")
                or campaign.get("industry")
                or campaign.get("name")
                or "botanica"
            )
            self._runtime_campaign_type = campaign_type
            self.safety_gate = InstagramSafetyGate(campaign_type)

            ok_posts, posts = self.prospecting_api._get(
                "prospecting/prospect-posts/",
                params={
                    "campaign_id": campaign_id,
                    "status": "relevant",
                    "analysis_status": "analyzed",
                    "is_relevant": "true",
                },
            )[:2]

            if not ok_posts:
                self.log.warning("No se pudieron consultar los prospect posts relevantes para comentar.")
                return False

            if not isinstance(posts, list):
                self.log.warning("La API devolvió un formato inválido para prospect posts | type=%s", type(posts).__name__)
                return False

            if not posts:
                # No tener trabajo elegible no es un fallo de la tarea.
                # Puede ocurrir normalmente después de que los posts elegibles
                # ya fueron comentados/procesados en ejecuciones anteriores.
                self.log.info(
                    "[prospecting-comment] no hay prospect posts nuevos/elegibles; tarea completada sin acciones | account_id=%s",
                    account_id,
                )
                self.log.info(
                    "[prospecting-comment] task finalizada | comentados=0 | account_id=%s",
                    account_id,
                )
                return True

            commented_total = 0
            max_to_process = 2

            for post in posts:
                if commented_total >= max_to_process:
                    break

                try:
                    prospect_id = post.get("prospect")
                    post_id = post.get("id")
                    post_url = str(post.get("post_url") or "").strip()
                    post_status = str(post.get("status") or "").strip().lower()

                    if not prospect_id or not post_id or not post_url:
                        continue

                    if post_status == "commented":
                        self.log.info(
                            "[prospecting-comment] post ya comentado, se omite | post_id=%s",
                            post_id,
                        )
                        continue

                    prospect_data = self._get_prospect_by_id(prospect_id)
                    if not prospect_data:
                        self.log.warning(
                            "[prospecting-comment] no se pudo obtener prospecto | prospect_id=%s",
                            prospect_id,
                        )
                        continue

                    profile_context = self._get_profile_context_for_prospect(prospect_data)

                    profile_context["campaign_services"] = campaign.get("services_snapshot") or []
                    profile_context["campaign_strategy"] = campaign.get("strategy_snapshot") or {}
                    profile_context["campaign_name"] = campaign.get("name") or ""

                    self.log.info(
                        "[prospecting-comment] profile_context=%s",
                        profile_context,
                    )

                    self.browser.go_to_url(post_url)
                    self.browser.time_sleep(random.randint(3, 5))

                    account_key = str(prospect_data.get("username") or prospect_data.get("id") or prospect_id or post_id)
                    allowed, gate_reason = self.safety_gate.allow("comment", account_key, commit=False)
                    if not allowed:
                        self.log.info("[safety-gate] comentario omitido: %s", gate_reason)
                        continue

                    ok_comment_ai, comment_text = (
                        self.comment_generation_service.generate_prospecting_comment_from_saved_post(
                            post=post,
                            profile_context=profile_context,
                            category="comentario_publicacion_prospecto",
                        )
                    )

                    if not ok_comment_ai or not comment_text:
                        self.log.warning(
                            "[prospecting-comment] no se pudo generar comentario IA | post_id=%s",
                            post_id,
                        )
                        continue

                    self.log.info(
                        "[prospecting-comment] comentario generado | post_id=%s | text=%s",
                        post_id,
                        comment_text,
                    )

                    self._sleep_config_delay("post_detected_to_intro_comment")
                    self.log.info(
                        "[prospecting-comment] stage=publish_comment | post_id=%s",
                        post_id,
                    )
                    ok_comment = self.post_interaction_service.comment_current_post(comment_text)
                    if ok_comment:
                        self.safety_gate.allow("comment", account_key, commit=True)
                    if not ok_comment:
                        self.log.warning(
                            "[prospecting-comment] falló comentario | post_id=%s | post_url=%s",
                            post_id,
                            post_url,
                        )
                        continue

                    self.browser.time_sleep(random.randint(1, 2))

                    can_like, like_reason = self.safety_gate.allow("like", account_key, commit=False)
                    if not can_like:
                        self.log.info("[safety-gate] like omitido: %s", like_reason)
                        ok_like = False
                    else:
                        self._sleep_config_delay("between_likes")
                        ok_like = self.post_interaction_service.like_current_post()
                        if ok_like:
                            self.safety_gate.allow("like", account_key, commit=True)
                    if not ok_like:
                        self.log.warning(
                            "[prospecting-comment] comentario salió bien pero like falló | post_id=%s | post_url=%s",
                            post_id,
                            post_url,
                        )

                    self.prospecting_api.create_prospect_interaction(
                        prospect_id=prospect_id,
                        prospect_post_id=post_id,
                        social_media_account_id=account_id,
                        interaction_type="commented",
                        direction="outbound",
                        content_text=comment_text,
                        status="success",
                    )

                    if ok_like:
                        self.prospecting_api.create_prospect_interaction(
                            prospect_id=prospect_id,
                            prospect_post_id=post_id,
                            social_media_account_id=account_id,
                            interaction_type="liked",
                            direction="outbound",
                            content_text="like",
                            status="success",
                        )

                    self.prospecting_api.update_prospect_post(
                        post_id,
                        status="commented",
                        commented_at=datetime.now(timezone.utc).isoformat(),
                        last_comment_text=comment_text,
                    )

                    self.prospecting_api.update_prospect(
                        prospect_id,
                        status="engaged",
                    )

                    commented_total += 1

                    self.log.info(
                        "[prospecting-comment] comentario publicado correctamente | post_id=%s | total=%s | account_id=%s",
                        post_id,
                        commented_total,
                        account_id,
                    )

                    self._sleep_config_delay("between_intro_comments")

                except Exception as e:
                    self.log.warning(
                        "[prospecting-comment] error procesando post=%s | error=%r",
                        post,
                        e,
                    )
                    continue
                finally:
                    # Ningún post/modal puede quedar abierto para contaminar
                    # la siguiente iteración o bloquear Search.
                    try:
                        self._cleanup_post_surface(post_id)
                    except Exception as cleanup_error:
                        self.log.warning(
                            "[post-cleanup] error inesperado | post_id=%s | error=%r",
                            post_id if "post_id" in locals() else None,
                            cleanup_error,
                        )

            self.log.info(
                "[prospecting-comment] task finalizada | comentados=%s | account_id=%s",
                commented_total,
                account_id,
            )

            return commented_total > 0

        except Exception as e:
            self.log.exception("Error en InstagramProspectCommentTask: %s", e)
            return False

    def _cleanup_post_surface(self, post_id=None) -> bool:
        """Return Instagram to a clean, dialog-free state after a post.

        Selenium can report detached/hidden ``role=dialog`` nodes that remain
        in Instagram's SPA DOM.  Cleanup therefore uses a browser-side
        visibility check and closes the *currently visible* dialog rather than
        treating every matching DOM node as an active overlay.
        """
        self.log.info(
            "[prospecting-comment] stage=cleanup_post_surface | post_id=%s",
            post_id,
        )

        driver = getattr(self.browser, "driver", None)
        if driver is None:
            return True

        visible_dialog_script = r"""
        return (() => {
            const visible = (el) => {
                if (!el) return false;
                const s = window.getComputedStyle(el);
                if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity || 1) === 0) return false;
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            };
            return [...document.querySelectorAll('[role="dialog"]')].some(visible);
        })();
        """

        def dialogs_open():
            try:
                result = self.browser.execute_script_safe(visible_dialog_script)
                return bool(result)
            except Exception:
                # Conservative fallback: Selenium's displayed state, but do
                # not count elements explicitly hidden by aria-hidden.
                try:
                    for dialog in driver.find_elements("xpath", "//*[@role='dialog']"):
                        try:
                            if dialog.get_attribute("aria-hidden") == "true":
                                continue
                            if dialog.is_displayed():
                                return True
                        except Exception:
                            continue
                except Exception:
                    pass
                return False

        def press_escape():
            try:
                body = driver.find_element("tag name", "body")
                body.send_keys("\ue00c")
                return True
            except Exception:
                try:
                    return bool(self.browser.execute_script_safe(
                        """document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',code:'Escape',bubbles:true,cancelable:true}));"""
                    ))
                except Exception:
                    return False

        def click_visible_close():
            # Instagram changes the exact close button markup frequently.  Do
            # the lookup/click atomically in the current DOM to avoid stale
            # Selenium elements.
            script = r"""
            return (() => {
                const visible = (el) => {
                    if (!el) return false;
                    const s = getComputedStyle(el);
                    if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity || 1) === 0) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                };
                const dialogs = [...document.querySelectorAll('[role="dialog"]')].filter(visible);
                if (!dialogs.length) return false;
                const dialog = dialogs[dialogs.length - 1];
                const candidates = [...dialog.querySelectorAll('button,[role="button"],svg')];
                const closeWords = /^(close|cerrar|dismiss|cancel|salir|x)$/i;
                for (const el of candidates) {
                    const label = [el.getAttribute('aria-label'), el.getAttribute('title'), el.textContent]
                        .filter(Boolean).join(' ').trim();
                    if (closeWords.test(label) || /\b(close|cerrar|dismiss|cancel|salir)\b/i.test(label)) {
                        const target = el.closest('button,[role="button"]') || el;
                        if (visible(target)) { target.click(); return true; }
                    }
                }
                // If this is a post surface, Instagram commonly exposes an
                // unlabeled top-right button. Prefer the first visible button
                // in the dialog header rather than arbitrary dialog content.
                const header = dialog.querySelector('header');
                if (header) {
                    const button = [...header.querySelectorAll('button,[role="button"]')].find(visible);
                    if (button) { button.click(); return true; }
                }
                return false;
            })();
            """
            try:
                return bool(self.browser.execute_script_safe(script))
            except Exception:
                return False

        # Phase 1: normal Escape dismissal.
        for _ in range(2):
            if not dialogs_open():
                break
            press_escape()
            self.browser.time_sleep(0.8)

        # Phase 2: DOM-native close.
        for _ in range(3):
            if not dialogs_open():
                break
            if not click_visible_close():
                break
            self.browser.time_sleep(0.8)

        # Phase 3: hard navigation.  Prefer the driver's real navigation API
        # so a React history state cannot leave the post modal mounted.
        if dialogs_open():
            try:
                if hasattr(driver, "get"):
                    driver.get("https://www.instagram.com/")
                else:
                    self.browser.go_to_url("https://www.instagram.com/")
                self.browser.time_sleep(2.0)
            except Exception as e:
                self.log.warning("[post-cleanup] error navegando a Home | error=%r", e)

        # Phase 4: one final refresh if a real visible dialog survives.
        if dialogs_open():
            try:
                driver.refresh()
                self.browser.time_sleep(2.0)
            except Exception:
                pass

        clean = not dialogs_open()
        current_url = str(getattr(driver, "current_url", "") or "")
        if not clean:
            self.log.warning(
                "[post-cleanup] could not guarantee clean state | url=%s | dialog=True",
                current_url,
            )
        else:
            self.log.info(
                "[post-cleanup] clean state confirmed | url=%s",
                current_url,
            )
        return clean

    def _get_social_media_account_id(self):
        try:
            social_media_account = self.data.get("social_media_account") or {}

            if isinstance(social_media_account, dict):
                account_id = social_media_account.get("id")
                if account_id:
                    return int(account_id)

            account_id = self.data.get("social_media_account_id")
            if account_id:
                return int(account_id)

            return None
        except Exception:
            return None

    def _get_prospect_by_id(self, prospect_id: int) -> dict | None:
        try:
            ok, payload = self.prospecting_api._get(
                f"prospecting/prospects/{prospect_id}/"
            )[:2]

            if ok and isinstance(payload, dict):
                return payload

            return None
        except Exception as e:
            self.log.warning(
                "[prospecting-comment] error obteniendo prospect_id=%s | error=%r",
                prospect_id,
                e,
            )
            return None

    def _get_profile_context_for_prospect(self, prospect_data: dict) -> dict:
        """
        Usa el perfil del prospecto para sacar contexto real del perfil.
        Si falla, usa fallback con lo que ya tienes guardado en BD.
        """
        profile_url = str(prospect_data.get("profile_url") or "").strip()

        fallback = {
            "profile_description": str(prospect_data.get("bio") or "").strip(),
            "profile_name": str(prospect_data.get("display_name") or "").strip(),
            "username": str(prospect_data.get("username") or "").strip(),
        }

        if not profile_url:
            return fallback

        try:
            self.browser.go_to_url(profile_url)
            self.browser.time_sleep(random.randint(3, 5))

            profile_context = self.post_media_service.get_current_profile_description_context()
            if isinstance(profile_context, dict):
                return profile_context

            return fallback

        except Exception as e:
            self.log.warning(
                "[prospecting-comment] error sacando profile_context real | profile_url=%s | error=%r",
                profile_url,
                e,
            )
            return fallback