import json
import random
import time
from datetime import datetime, timezone
from typing import Optional

from app.utils.logger import get_logger
from app.utils.instagram_url import (
    _normalize_instagram_href,
    _extract_username_from_url,
)
from app.api.prospecting_api import ProspectingAPI
from app.services.instagram_profile_service import InstagramProfileService
from app.services.instagram_post_media_service import InstagramPostMediaService
from app.services.instagram_post_interaction_service import InstagramPostInteractionService
from app.services.instagram_comment_generation_service import InstagramCommentGenerationService
from .instagram_followback.instagram_followback_navigation import (
    InstagramFollowbackNavigationMixin,
)
from .instagram_followback.instagram_followback_text import InstagramFollowbackTextMixin
from app.services.instagram_prospect_classification_service import (
    InstagramProspectClassificationService,
)
from app.services.instagram_campaign_policy_service import InstagramCampaignPolicyService
from app.services.instagram_safety_gate import InstagramSafetyGate
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService

class InstagramProspectDiscoveryTask(
    InstagramFollowbackNavigationMixin,
    InstagramFollowbackTextMixin,
):
    """
    Discovery + follow + comment para prospectación Instagram.

    Flujo único:
    - toma campaña activa por social_media_account.id
    - usa hashtags desde strategy_snapshot
    - abre publicaciones candidatas
    - extrae post + perfil + posts recientes
    - califica con IA
    - guarda prospecto y prospect_post
    - si el prospecto es válido:
        - sigue al prospecto
        - vuelve al post descubierto
        - genera comentario IA
        - comenta ahí mismo
        - da like
        - registra interacciones
        - actualiza prospect_post a commented
        - actualiza prospect a engaged
    """

    MAX_POSTS_PER_RESULT = 3
    MAX_TOTAL_ENGAGED = 5
    MIN_SCORE_TO_ENGAGE = 6

    # Un 429 debe detener el discovery de esta ejecución. Continuar
    # probando hashtags solo aumenta el rate limit y puede prolongarlo.

    def __init__(self, browser, ai_api, account_api, data: dict):
        self.browser = browser
        self.ai_api = ai_api
        self.account_api = account_api
        self.data = data or {}
        self.log = get_logger(self.__class__.__name__)
        self._rate_limited = False
        # First follow in a task must not wait for the configured inter-follow delay.
        # The delay applies only between two actual follow actions.
        self._last_follow_action_at = None

        self.prospecting_api = ProspectingAPI()

        self.profile_service = InstagramProfileService(
            browser=self.browser,
            logger=self.log,
        )
        self.classification_service = InstagramProspectClassificationService(
            ai_api=self.ai_api,
            logger=self.log,
        )

        self.post_media_service = InstagramPostMediaService(
            browser=self.browser,
            ai_api=self.ai_api,
            logger=self.log,
        )

        self.post_interaction_service = InstagramPostInteractionService(
            browser=self.browser,
            logger=self.log,
        )

        self.comment_generation_service = InstagramCommentGenerationService(
            data=self.data,
            account_api=self.account_api,
            ai_api=self.ai_api,
            post_media_service=self.post_media_service,
            logger=self.log,
        )

        self.current_search_term = ""
        self.current_campaign = None
        self.current_social_media_account_id = None
        self.safety_gate = InstagramSafetyGate(InstagramConfigRuntimeService.campaign(self.data.get("campaign_type") or "botanica"))
        # Persistent within one task execution: prevent the same post/profile
        # from being classified repeatedly when it appears under multiple hashtags.
        self._seen_post_urls = set()
        self._seen_usernames = set()

    @staticmethod
    def _campaign_account_matches(campaign: dict, execution_account_id) -> bool:
        """Validate the account invariant before any browser work begins."""
        try:
            configured = (campaign or {}).get("social_media_account")
            configured_id = (
                configured.get("id") if isinstance(configured, dict) else configured
            )
            if configured_id is None:
                # Legacy campaigns may not carry the denormalized account field.
                # The API lookup remains the source of truth in that case.
                return True
            return int(configured_id) == int(execution_account_id)
        except (TypeError, ValueError):
            return False

    # =========================================================
    # ENTRYPOINT
    # =========================================================
    def execute(self) -> bool:
        try:
            self._seen_post_urls.clear()
            self._seen_usernames.clear()
            social_media_account = self._get_social_media_account()
            account_id = social_media_account.get("id")

            if not account_id:
                self.log.warning("No se encontró social_media_account.id")
                return False

            self.current_social_media_account_id = int(account_id)

            self.log.info("[prospecting] account_id=%s", account_id)

            ok_campaign, campaign = self.prospecting_api.get_active_campaign(
                social_media_account_id=account_id,
                platform="instagram",
            )

            self.log.info(
                "[prospecting] get_active_campaign | ok=%s | campaign=%s",
                ok_campaign,
                self._shorten_for_log(campaign),
            )

            if not ok_campaign or not isinstance(campaign, dict):
                self.log.warning("No se encontró campaña activa: %s", campaign)
                return False

            # Hard integrity invariant: campaign, execution session and
            # persistence must all use the same social-media account.
            if not self._campaign_account_matches(campaign, account_id):
                configured = campaign.get("social_media_account")
                configured_id = (
                    configured.get("id") if isinstance(configured, dict) else configured
                )
                self.log.error(
                    "[account-integrity] BLOQUEADO campaign/account mismatch | "
                    "campaign_account=%s | execution_account=%s | campaign_id=%s",
                    configured_id, account_id, campaign.get("id"),
                )
                return False

            self.current_campaign = campaign
            strategy = campaign.get("strategy_snapshot") or {}
            campaign_type = InstagramConfigRuntimeService.campaign(
                campaign.get("campaign_type")
                or campaign.get("industry_target")
                or campaign.get("industry")
                or strategy.get("campaign_type")
                or campaign.get("type")
                or self.data.get("campaign_type")
                or "botanica"
            )
            self.safety_gate = InstagramSafetyGate(campaign_type)

            configured_hashtags = self._extract_hashtags_from_strategy(strategy)
            # The migrated 03 file remains the canonical fallback source.
            if not configured_hashtags:
                discovery_policy = InstagramCampaignPolicyService.load_discovery_policy(campaign_type)
                configured_hashtags = [
                    item.get("tag")
                    for category in discovery_policy.get("categories") or []
                    for item in (category.get("hashtags") or [])
                    if isinstance(item, dict) and item.get("tag")
                ]

            hashtags, rejected_hashtags = InstagramCampaignPolicyService.filter_hashtags(
                configured_hashtags, strategy, campaign_type
            )

            for rejected_tag, reason in rejected_hashtags:
                self.log.info(
                    "[hashtag-policy] descartado | campaign_type=%s | hashtag=%s | reason=%s",
                    campaign_type, rejected_tag, reason,
                )

            if not hashtags:
                self.log.warning(
                    "La campaña no tiene hashtags válidos según 03_discovery_hashtags.json | campaign_type=%s",
                    campaign_type,
                )
                return False

            self.log.info(
                "Campaña activa encontrada | id=%s | hashtags=%s | account_id=%s",
                campaign.get("id"),
                hashtags,
                self.current_social_media_account_id,
            )

            engaged_total = 0

            for hashtag in hashtags:
                if self._rate_limited or self.profile_service.is_rate_limited():
                    self.log.warning(
                        "[instagram-rate-limit] discovery detenido; no se procesarán más hashtags en esta ejecución."
                    )
                    break

                if engaged_total >= self.MAX_TOTAL_ENGAGED:
                    self.log.info(
                        "[prospecting] tope global alcanzado | engaged_total=%s | max_total=%s",
                        engaged_total,
                        self.MAX_TOTAL_ENGAGED,
                    )
                    break

                self.current_search_term = hashtag.strip()

                if not self.current_search_term:
                    continue

                remaining = self.MAX_TOTAL_ENGAGED - engaged_total

                if remaining <= 0:
                    break

                self.log.info(
                    "Iniciando discovery+engagement con hashtag: %s | remaining=%s",
                    self.current_search_term,
                    remaining,
                )

                if not self._open_search_button():
                    self.log.warning(
                        "[search-ui] no se pudo abrir búsqueda | intento de recuperación antes de abandonar discovery"
                    )
                    recovered = self.recover_from_post_surface()
                    if recovered and self._open_search_button():
                        self.log.info("[search-ui] búsqueda recuperada tras fallo de UI")
                    else:
                        self.log.error(
                            "[search-ui] ABORTADO discovery: buscador no disponible tras recuperación"
                        )
                        break

                if not self._type_search_term():
                    self.log.warning("No se pudo escribir el término de búsqueda.")
                    continue

                result_hrefs = self._collect_hashtag_result_hrefs()

                self.log.info(
                    "[prospecting] result_hrefs hashtag=%s | count=%s | hrefs=%s",
                    self.current_search_term,
                    len(result_hrefs or []),
                    self._shorten_for_log(result_hrefs),
                )

                if not result_hrefs:
                    self.log.warning(
                        "No se encontraron resultados para hashtag: %s",
                        self.current_search_term,
                    )
                    continue

                requested_slug = self._normalize_hashtag_slug(self.current_search_term)
                exact_hrefs = [
                    href for href in result_hrefs
                    if self._hashtag_href_matches_slug(href, requested_slug)
                ]
                if len(exact_hrefs) != 1:
                    self.log.error(
                        "[hashtag-validation] BLOQUEADO selección ambigua | requested=%s | exact_hrefs=%s",
                        self.current_search_term, exact_hrefs,
                    )
                    continue

                hashtag_href = exact_hrefs[0]

                # _collect_hashtag_result_hrefs() ya aplica coincidencia exacta.
                # Esta segunda barrera evita que una regresión futura vuelva a
                # abrir un hashtag recomendado/ajeno al término solicitado.
                if not self._hashtag_href_matches_slug(
                    hashtag_href,
                    self._normalize_hashtag_slug(self.current_search_term),
                ):
                    self.log.error(
                        "[hashtag-validation] BLOQUEADO destino no coincidente | solicitado=%s | href=%s",
                        self.current_search_term,
                        hashtag_href,
                    )
                    continue

                self.log.info(
                    "Abriendo resultado exacto para %s | href=%s",
                    self.current_search_term,
                    hashtag_href,
                )

                if not self._open_hashtag_result_by_href(hashtag_href):
                    self.log.warning(
                        "No se pudo abrir el primer resultado para %s",
                        self.current_search_term,
                    )
                    continue

                self.browser.time_sleep(3)

                max_posts_this_round = min(self.MAX_POSTS_PER_RESULT, remaining)

                engaged_here = self._scan_result_posts(
                    result_href=hashtag_href,
                    max_posts=max_posts_this_round,
                )

                engaged_total += engaged_here

                self.log.info(
                    "Resultado procesado | hashtag=%s | engaged_en_resultado=%s | acumulado=%s | remaining=%s",
                    self.current_search_term,
                    engaged_here,
                    engaged_total,
                    self.MAX_TOTAL_ENGAGED - engaged_total,
                )

                if engaged_total >= self.MAX_TOTAL_ENGAGED:
                    self.log.info(
                        "[prospecting] corte exacto aplicado | engaged_total=%s",
                        engaged_total,
                    )
                    break

            self.log.info("Discovery+engagement finalizado | total_engaged=%s", engaged_total)
            return engaged_total > 0

        except Exception as e:
            self.log.exception("Error en InstagramProspectDiscoveryTask: %s", e)
            return False

    # =========================================================
    # STRATEGY
    # =========================================================
    def _extract_hashtags_from_strategy(self, strategy: dict) -> list[str]:
        hashtags = strategy.get("hashtags") or []

        if isinstance(hashtags, str):
            hashtags = [hashtags]

        normalized = []
        seen = set()

        for item in hashtags:
            tag = str(item or "").strip()

            if not tag:
                continue

            if not tag.startswith("#"):
                tag = f"#{tag}"

            if tag.lower() in seen:
                continue

            seen.add(tag.lower())
            normalized.append(tag)

        return normalized

    def _get_search_term(self) -> str:
        return self.current_search_term

    # =========================================================
    # SCAN GRID
    # =========================================================
    def _scan_result_posts(self, result_href: str, max_posts: int = 3) -> int:
        tried_hrefs = set()
        engaged = 0

        for attempt in range(1, max_posts + 1):
            try:
                self.log.info(
                    "Abriendo publicación candidata %s/%s para %s",
                    attempt,
                    max_posts,
                    self.current_search_term,
                )

                opened_href = self._open_next_post_from_hashtag_grid(
                    excluded_hrefs=tried_hrefs,
                )

                if not opened_href:
                    self.log.warning("No se pudo abrir una nueva publicación candidata.")
                    break

                opened_href = _normalize_instagram_href(opened_href)
                if not opened_href or opened_href in self._seen_post_urls:
                    self.log.info("[prospecting] post duplicado omitido | url=%s", opened_href)
                    tried_hrefs.add(opened_href)
                    continue
                self._seen_post_urls.add(opened_href)
                tried_hrefs.add(opened_href)

                self.log.info(
                    "[prospecting] opened_href=%s | tried_hrefs_count=%s",
                    opened_href,
                    len(tried_hrefs),
                )

                self.browser.time_sleep(3)

                post_context = self.profile_service.extract_current_post_context(opened_href)

                self.log.info(
                    "[prospecting] post_context=%s",
                    self._shorten_for_log(post_context),
                )

                if not post_context:
                    self.log.warning("No se pudo extraer contexto del post: %s", opened_href)
                    self._return_to_result_grid(result_href)
                    continue

                profile_context = self.profile_service.extract_author_profile_context(
                    post_context
                )

                self.log.info(
                    "[prospecting] profile_context=%s",
                    self._shorten_for_log(profile_context),
                )

                if not profile_context:
                    self.log.warning("No se pudo extraer contexto del perfil del autor.")
                    self._return_to_result_grid(result_href)
                    continue

                username = str(profile_context.get("username") or "").strip().lower()
                if username and username in self._seen_usernames:
                    self.log.info("[prospecting] perfil duplicado omitido | username=%s", username)
                    self._return_to_result_grid(result_href)
                    continue
                if username:
                    self._seen_usernames.add(username)

                # Conservative early screening: do not spend recent-post/AI
                # resources on an account that is explicitly personal/employee.
                if self.classification_service._looks_like_personal_employee(
                    profile_context, post_context, []
                ):
                    qualification = self.classification_service._build_personal_skip_result(
                        self.classification_service.detect_campaign_industry(self.current_campaign or {}),
                        self.current_campaign or {},
                    )
                    qualification["qualification_reason"] = "Cuenta personal vinculada a un empleador; no se trata como negocio propio."
                    qualification["post_reason"] = qualification["qualification_reason"]
                    save_result = self._save_discovered_candidate(post_context, profile_context, qualification)
                    self.log.info("[prospecting] early personal/employee discard | username=%s", username)
                    self._return_to_result_grid(result_href)
                    continue

                recent_posts = self._collect_recent_profile_posts(
                    profile_url=profile_context["profile_url"],
                    current_post_url=post_context["post_url"],
                    max_posts=3,
                )

                self.log.info(
                    "[prospecting] recent_posts=%s",
                    self._shorten_for_log(recent_posts, max_len=3000),
                )

                qualification = self._qualify_candidate_with_ai(
                    post_context=post_context,
                    profile_context=profile_context,
                    recent_posts=recent_posts,
                )

                save_result = self._save_discovered_candidate(
                    post_context=post_context,
                    profile_context=profile_context,
                    qualification=qualification,
                )

                self.log.info(
                    "[prospecting] save_result=%s",
                    self._shorten_for_log(save_result),
                )

                self.log.info("[prospecting-debug] after_save_result | post_id=%s", save_result.get("prospect_post", {}).get("id"))

                if not save_result.get("ok"):
                    self.log.info("[prospecting-debug] save_result_failed | post_id=%s", save_result.get("prospect_post", {}).get("id"))
                    self._return_to_result_grid(result_href)
                    continue

                self.log.info("[prospecting-debug] before_no_response_check | post_id=%s", save_result.get("prospect_post", {}).get("id"))
                if self._no_response_like_only(save_result):
                    self.log.info("[prospecting-debug] entering_like_only | post_id=%s", save_result.get("prospect_post", {}).get("id"))
                    self._inline_like_only_candidate(post_context, profile_context, save_result)
                    self._return_to_result_grid(result_href)
                    continue

                self.log.info("[prospecting-debug] before_should_inline_engage | post_id=%s", save_result.get("prospect_post", {}).get("id"))
                if not self._should_inline_engage(
                    qualification=qualification,
                    save_result=save_result,
                ):
                    self.log.info(
                        "[prospecting] candidato guardado pero no se engagea | username=%s | qualification=%s",
                        profile_context.get("username"),
                        self._shorten_for_log(qualification),
                    )
                    self._return_to_result_grid(result_href)
                    continue

                self.log.info(
                    "[prospecting-debug] entering_inline_follow_comment | post_id=%s | username=%s",
                    save_result.get("prospect_post", {}).get("id"),
                    profile_context.get("username"),
                )
                ok_engage = self._inline_follow_and_comment_candidate(
                    post_context=post_context,
                    profile_context=profile_context,
                    qualification=qualification,
                    save_result=save_result,
                )
                self.log.info("[prospecting-debug] returned_inline_follow_comment | post_id=%s | ok=%s",
                              save_result.get("prospect_post", {}).get("id"), ok_engage)

                if ok_engage:
                    engaged += 1

                self._return_to_result_grid(result_href)
                self._sleep_config_delay("between_intro_comments")

            except Exception as e:
                if self.profile_service.is_rate_limited():
                    self._rate_limited = True
                    self.log.warning(
                        "[instagram-rate-limit] candidato detenido por 429: %r",
                        e,
                    )
                    break
                self.log.warning("Error escaneando publicación candidata: %r", e)
                self._return_to_result_grid(result_href)

        return engaged

    def _sleep_config_delay(self, action: str) -> None:
        campaign_type = InstagramConfigRuntimeService.campaign(
            (self.current_campaign or {}).get("campaign_type")
            or (self.current_campaign or {}).get("industry_target")
            or (self.current_campaign or {}).get("industry")
            or "botanica"
        )
        delay = InstagramConfigRuntimeService.delay(campaign_type, action)
        if not delay:
            return
        try:
            minimum = float(delay.get("min", 0))
            maximum = float(delay.get("max", minimum))
            if maximum < minimum:
                minimum, maximum = maximum, minimum
            self.browser.time_sleep(random.uniform(minimum, maximum))
        except (TypeError, ValueError):
            return

    def _sleep_between_follows_if_needed(self) -> None:
        """Apply the configured inter-follow delay only after a prior follow.

        ``between_follows`` is a spacing rule, not a mandatory preflight wait.
        Waiting before the first follow made a real task appear frozen for
        240-540 seconds because the botanica fallback config is selected when
        the campaign has no explicit campaign_type.
        """
        if self._last_follow_action_at is None:
            self.log.info(
                "[prospecting-delay] first follow: no between_follows wait"
            )
            return
        self.log.info(
            "[prospecting-delay] waiting configured between_follows before next follow"
        )
        self._sleep_config_delay("between_follows")

    def _no_response_like_only(self, save_result: dict) -> bool:
        prospect = save_result.get("prospect") or {}
        prospect_post = save_result.get("prospect_post") or {}
        campaign_type = InstagramConfigRuntimeService.campaign(
            (self.current_campaign or {}).get("campaign_type")
            or (self.current_campaign or {}).get("industry_target")
            or (self.current_campaign or {}).get("industry")
            or "botanica"
        )
        if not InstagramConfigRuntimeService.likes_only_after_no_response(campaign_type):
            return False
        return str(prospect.get("status") or "").lower() == "no_response" or str(prospect_post.get("status") or "").lower() == "no_response"

    def _inline_like_only_candidate(self, post_context: dict, profile_context: dict, save_result: dict) -> bool:
        prospect = save_result.get("prospect") or {}
        prospect_post = save_result.get("prospect_post") or {}
        prospect_id = prospect.get("id")
        post_id = prospect_post.get("id")
        post_url = str(post_context.get("post_url") or "").strip()
        account_key = str(prospect.get("username") or prospect_id or post_id)
        if not prospect_id or not post_id or not post_url:
            return False
        allowed, reason = self.safety_gate.allow("like", account_key, commit=False)
        if not allowed:
            self.log.info("[likes-only] like omitido: %s", reason)
            return False
        self.browser.go_to_url(post_url)
        self._sleep_config_delay("between_likes")
        ok = self.post_interaction_service.like_current_post()
        if ok:
            self.safety_gate.allow("like", account_key, commit=True)
            self.prospecting_api.create_prospect_interaction(
                prospect_id=prospect_id, prospect_post_id=post_id,
                social_media_account_id=self.current_social_media_account_id,
                interaction_type="liked", direction="outbound", content_text="like_only_no_response", status="success"
            )
            self.prospecting_api.update_prospect_post(post_id, status="no_response")
        return bool(ok)

    def _should_inline_engage(self, qualification: dict, save_result: dict) -> bool:
        try:
            if not qualification.get("is_valid"):
                return False

            score = self._safe_float(
                qualification.get("qualification_score"),
                default=0.0,
            )

            if score < self.MIN_SCORE_TO_ENGAGE:
                self.log.info(
                    "[prospecting] score bajo para engage | score=%s | min=%s",
                    score,
                    self.MIN_SCORE_TO_ENGAGE,
                )
                return False

            prospect = save_result.get("prospect") or {}
            prospect_post = save_result.get("prospect_post") or {}
            status = str(prospect_post.get("status") or "").strip().lower()
            if str(prospect.get("status") or "").strip().lower() == "no_response":
                return False

            if status in {"commented", "no_response", "follow_up_pending", "human_takeover"}:
                self.log.info(
                    "[prospecting] prospect_post ya estaba commented | post_id=%s",
                    prospect_post.get("id"),
                )
                return False

            return True

        except Exception as e:
            self.log.warning("[prospecting] error en _should_inline_engage: %r", e)
            return False

    # =========================================================
    # INLINE FOLLOW + COMMENT
    # =========================================================
    def _inline_follow_and_comment_candidate(
        self,
        post_context: dict,
        profile_context: dict,
        qualification: dict,
        save_result: dict,
    ) -> bool:
        prospect = save_result.get("prospect") or {}
        prospect_post = save_result.get("prospect_post") or {}

        prospect_id = prospect.get("id")
        prospect_post_id = prospect_post.get("id")
        post_url = str(post_context.get("post_url") or "").strip()
        profile_url = str(profile_context.get("profile_url") or "").strip()

        if not prospect_id or not prospect_post_id or not post_url:
            self.log.warning(
                "[prospecting-inline] faltan IDs/URL | prospect_id=%s | post_id=%s | post_url=%s",
                prospect_id,
                prospect_post_id,
                post_url,
            )
            return False

        account_id = self.current_social_media_account_id

        try:
            account_key = str(prospect.get("username") or prospect_id or "")
            can_follow, follow_reason = self.safety_gate.allow("follow", account_key, commit=False)
            if not can_follow:
                self.log.info("[safety-gate] follow omitido: %s", follow_reason)
                return False

            self._sleep_between_follows_if_needed()
            self.log.info("[prospecting-debug] before_follow | username=%s | profile_url=%s", account_key, profile_url)
            follow_status = self.profile_service.ensure_follow_profile(profile_url)
            self.log.info("[prospecting-debug] after_ensure_follow_profile | username=%s | status=%s", account_key, follow_status)
            followed = follow_status in {"followed", "already_following"}

            if follow_status == "followed":
                self.safety_gate.allow("follow", account_key, commit=True)
                self._last_follow_action_at = time.monotonic()
                self.log.info("[prospecting-debug] follow_action_recorded | username=%s | status=%s", account_key, follow_status)

            if followed:
                self.prospecting_api.create_prospect_interaction(
                    prospect_id=prospect_id,
                    prospect_post_id=prospect_post_id,
                    social_media_account_id=account_id,
                    interaction_type="followed",
                    direction="outbound",
                    content_text=follow_status,
                    status="success",
                )
            else:
                self.log.warning(
                    "[prospecting-inline] no se pudo seguir prospecto | profile_url=%s | follow_status=%s",
                    profile_url,
                    follow_status,
                )
                return False

            self.log.info("[prospecting-debug] before_return_to_post | post_id=%s", prospect_post_id)
            self.profile_service.open_url(post_url)
            self.log.info("[prospecting-debug] after_return_to_post | post_id=%s", prospect_post_id)
            self.browser.time_sleep(random.randint(3, 5))

            profile_context_for_comment = dict(profile_context or {})
            profile_context_for_comment["campaign_services"] = (
                self.current_campaign.get("services_snapshot")
                if self.current_campaign
                else []
            ) or []
            profile_context_for_comment["campaign_strategy"] = (
                self.current_campaign.get("strategy_snapshot")
                if self.current_campaign
                else {}
            ) or {}
            profile_context_for_comment["campaign_name"] = (
                self.current_campaign.get("name")
                if self.current_campaign
                else ""
            ) or ""

            post_for_comment = dict(prospect_post or {})
            post_for_comment.setdefault("id", prospect_post_id)
            post_for_comment.setdefault("post_url", post_url)
            post_for_comment.setdefault(
                "caption_text",
                post_context.get("caption_text", ""),
            )
            post_for_comment.setdefault(
                "post_type",
                post_context.get("post_type", "post"),
            )

            ok_comment_ai, comment_text = (
                self.comment_generation_service.generate_prospecting_comment_from_saved_post(
                    post=post_for_comment,
                    profile_context=profile_context_for_comment,
                    category="comentario_publicacion_prospecto",
                )
            )

            if not ok_comment_ai or not comment_text:
                self.log.warning(
                    "[prospecting-inline] no se pudo generar comentario IA | post_id=%s",
                    prospect_post_id,
                )
                return False

            comment_text = str(comment_text or "").strip()

            self.log.info(
                "[prospecting-inline] comentario generado | post_id=%s | text=%s",
                prospect_post_id,
                comment_text,
            )

            can_comment, comment_reason = self.safety_gate.allow(
                "comment", account_key, commit=False
            )
            if not can_comment:
                self.log.info("[safety-gate] comentario omitido: %s", comment_reason)
                return False

            self._sleep_config_delay("post_detected_to_intro_comment")
            ok_comment = self.post_interaction_service.comment_current_post(
                comment_text
            )
            if ok_comment:
                self.safety_gate.allow("comment", account_key, commit=True)

            if not ok_comment:
                self.log.warning(
                    "[prospecting-inline] falló comentario | post_id=%s | post_url=%s",
                    prospect_post_id,
                    post_url,
                )
                return False

            self.browser.time_sleep(random.randint(1, 2))

            can_like, like_reason = self.safety_gate.allow(
                "like", account_key, commit=False
            )
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
                    "[prospecting-inline] comentario salió bien pero like falló | post_id=%s | post_url=%s",
                    prospect_post_id,
                    post_url,
                )

            self.prospecting_api.create_prospect_interaction(
                prospect_id=prospect_id,
                prospect_post_id=prospect_post_id,
                social_media_account_id=account_id,
                interaction_type="commented",
                direction="outbound",
                content_text=comment_text,
                status="success",
            )

            if ok_like:
                self.prospecting_api.create_prospect_interaction(
                    prospect_id=prospect_id,
                    prospect_post_id=prospect_post_id,
                    social_media_account_id=account_id,
                    interaction_type="liked",
                    direction="outbound",
                    content_text="like",
                    status="success",
                )

            self.prospecting_api.update_prospect_post(
                prospect_post_id,
                status="commented",
                commented_at=datetime.now(timezone.utc).isoformat(),
                last_comment_text=comment_text,
            )

            self.prospecting_api.update_prospect(
                prospect_id,
                status="engaged",
            )

            self.log.info(
                "[prospecting-inline] follow+comment completado | prospect_id=%s | post_id=%s | followed=%s | liked=%s",
                prospect_id,
                prospect_post_id,
                followed,
                ok_like,
            )

            self.browser.time_sleep(random.randint(2, 4))
            return True

        except Exception as e:
            self.log.warning(
                "[prospecting-inline] error en follow+comment | prospect_id=%s | post_id=%s | error=%r",
                prospect_id,
                prospect_post_id,
                e,
            )
            return False

    # =========================================================
    # RECENT POSTS
    # =========================================================
    def _collect_recent_profile_posts(
        self,
        profile_url: str,
        current_post_url: str,
        max_posts: int = 3,
    ) -> list[dict]:
        recent_posts = []

        try:
            if not profile_url:
                self.log.warning("[prospecting] profile_url vacío al recolectar recent_posts")
                return recent_posts

            profile_username = (_extract_username_from_url(profile_url) or "").strip().lower()

            targets = self.profile_service.collect_profile_grid_post_targets(
                profile_url=profile_url,
                profile_username=profile_username,
                limit=max_posts + 2,
            )

            self.log.info(
                "[prospecting] profile_grid_targets | profile_url=%s | count=%s | targets=%s",
                profile_url,
                len(targets),
                self._shorten_for_log(targets, max_len=3000),
            )

            current_shortcode = self.profile_service.extract_shortcode_from_post_url(
                current_post_url
            )

            filtered_targets = []
            seen_targets = set()

            for target in targets:
                target = _normalize_instagram_href(target)
                if not target or target in seen_targets or target in self._seen_post_urls:
                    continue
                seen_targets.add(target)
                shortcode = self.profile_service.extract_shortcode_from_post_url(target)

                if current_shortcode and shortcode == current_shortcode:
                    continue

                filtered_targets.append(target)

            for target in filtered_targets[:max_posts]:
                try:
                    if not self.profile_service.open_recent_post_from_profile_grid(
                        profile_url=profile_url,
                        target_url=target,
                        expected_author_username=profile_username,
                    ):
                        self.profile_service.recover_from_post_surface()
                        continue

                    self.browser.time_sleep(random.uniform(2.0, 3.0))

                    context = self.profile_service.extract_recent_post_context(
                        expected_url=target,
                        expected_author_username=profile_username,
                    )

                    if context:
                        recent_posts.append(context)
                    else:
                        self.log.warning(
                            "[profile-integrity] recent post rechazado tras extracción | profile=%s | target=%s",
                            profile_username, target,
                        )
                        self.profile_service.recover_from_post_surface()

                    self.browser.time_sleep(random.uniform(1.0, 2.0))

                except Exception as e:
                    self.log.warning(
                        "[prospecting] error procesando recent post target=%s | error=%r",
                        target,
                        e,
                    )
                    continue

        except Exception as e:
            self.log.warning(
                "[prospecting] error recolectando recent_posts | profile_url=%s | error=%r",
                profile_url,
                e,
            )

        finally:
            try:
                if self.profile_service.is_rate_limited() or self._rate_limited:
                    self.log.warning(
                        "[instagram-rate-limit] no se navega de regreso al post para evitar otro 429."
                    )
                else:
                    self.profile_service.open_url(current_post_url)
                    self.browser.time_sleep(random.uniform(2.0, 3.0))
            except Exception as e:
                if isinstance(e, Exception) and self.profile_service.is_rate_limited():
                    self._rate_limited = True
                self.log.warning(
                    "[prospecting] no se pudo restaurar post actual | error=%r",
                    e,
                )

        self.log.info(
            "[prospecting] recent_posts_final=%s",
            self._shorten_for_log(recent_posts, max_len=4000),
        )

        return recent_posts

    # =========================================================
    # IA QUALIFICATION
    # =========================================================

    def _qualify_candidate_with_ai(
        self,
        post_context: dict,
        profile_context: dict,
        recent_posts: Optional[list[dict]] = None,
    ) -> dict:
        """
        Prepara el contexto del candidato y delega la clasificación
        al InstagramProspectClassificationService.

        Este método NO contiene las reglas de clasificación.
        El servicio de clasificación es responsable de:
        - detectar industria
        - evaluar competencia
        - clasificar perfil
        - clasificar rol
        - detectar vertical
        - medir intención comercial
        - aplicar reglas específicas por industria

        Aquí solamente:
        1. obtenemos el bot_personality_id
        2. enviamos campaña + perfil + post + posts recientes
        3. adaptamos la respuesta del clasificador al formato que
        el flujo existente de prospecting espera.
        """

        recent_posts = recent_posts or []

        try:
            campaign = self.current_campaign or {}

            bot_personality_id = self._get_bot_personality_id()

            if not bot_personality_id:
                self.log.warning(
                    "[prospecting] no se encontró bot_personality_id "
                    "para clasificación"
                )

                return {
                    "is_valid": False,
                    "industry_target": self.classification_service.detect_campaign_industry(campaign),
                    "industry_detected": "unknown",
                    "qualification_score": 0,
                    "qualification_reason": "Sin bot_personality_id",
                    "post_reason": "No se pudo clasificar con IA",

                    "skip_post": True,
                    "mode": "skip",
                    "selected_service": "",
                    "b2b_target_type": "",
                    "b2b_angle": "",
                    "b2b_confidence": "low",
                    "request_directness": "none",
                    "service_match_reason": "",
                    "comment": "",

                    "competitor_score": 0,
                    "is_competitor": False,
                    "is_blacklisted": False,
                    "blacklist_reason": "",
                    "profile_classification": "UNKNOWN",
                    "business_role": "UNKNOWN",
                    "business_vertical": "UNKNOWN",
                    "competitor_relation": "UNKNOWN",
                    "commercial_intent_score": 0,
                    "classification_confidence": 0,
                    "classification_evidence": [],
                }

            self.log.info(
                "[prospecting] delegando clasificación | "
                "username=%s | campaign_id=%s | bot_personality_id=%s",
                profile_context.get("username"),
                campaign.get("id"),
                bot_personality_id,
            )

            ok_classification, classification = (
                self.classification_service.classify(
                    bot_personality_id=bot_personality_id,
                    campaign=campaign,
                    profile_context=profile_context,
                    post_context=post_context,
                    recent_posts=recent_posts,
                )
            )

            self.log.info(
                "[prospecting] classification_service | "
                "ok=%s | result=%s",
                ok_classification,
                self._shorten_for_log(
                    classification,
                    max_len=4000,
                ),
            )

            if not ok_classification or not isinstance(classification, dict):
                self.log.warning(
                    "[prospecting] clasificación falló | result=%s",
                    self._shorten_for_log(classification),
                )

                return {
                    "is_valid": False,
                    "industry_target": self.classification_service.detect_campaign_industry(campaign),
                    "industry_detected": "unknown",
                    "qualification_score": 0,
                    "qualification_reason": str(
                        (classification or {}).get("error")
                        or "Error en clasificación"
                    ),
                    "post_reason": "No se pudo clasificar con IA",

                    "skip_post": True,
                    "mode": "skip",
                    "selected_service": "",
                    "b2b_target_type": "",
                    "b2b_angle": "",
                    "b2b_confidence": "low",
                    "request_directness": "none",
                    "service_match_reason": "",
                    "comment": "",

                    "competitor_score": 0,
                    "is_competitor": False,
                    "is_blacklisted": False,
                    "blacklist_reason": "",
                    "profile_classification": "UNKNOWN",
                    "business_role": "UNKNOWN",
                    "business_vertical": "UNKNOWN",
                    "competitor_relation": "UNKNOWN",
                    "commercial_intent_score": 0,
                    "classification_confidence": 0,
                    "classification_evidence": [],
                }

            # =====================================================
            # COMPATIBILITY / LEGACY MAPPING
            # =====================================================

            is_competitor = bool(
                classification.get("is_competitor")
                or classification.get("is_blacklisted")
            )

            competitor_relation = str(
                classification.get("competitor_relation")
                or "UNKNOWN"
            ).strip().upper()

            profile_classification = str(
                classification.get("profile_classification")
                or "UNKNOWN"
            ).strip().upper()

            business_role = str(
                classification.get("business_role")
                or "UNKNOWN"
            ).strip().upper()

            business_vertical = str(
                classification.get("business_vertical")
                or "UNKNOWN"
            ).strip().upper()

            industry_target = str(
                classification.get("industry_target")
                or self.classification_service.detect_campaign_industry(campaign)
                or "unknown"
            ).strip()
            industry_detected = str(
                classification.get("industry_detected")
                or business_vertical
                or "unknown"
            ).strip()

            competitor_score = self._safe_float(
                classification.get("competitor_score"),
                default=0.0,
            )

            commercial_intent_score = self._safe_float(
                classification.get("commercial_intent_score"),
                default=0.0,
            )

            classification_confidence = self._safe_float(
                classification.get("classification_confidence"),
                default=0.0,
            )

            classification_evidence = classification.get(
                "classification_evidence"
            )

            if not isinstance(classification_evidence, list):
                classification_evidence = []

            blacklist_reason = str(
                classification.get("blacklist_reason")
                or ""
            ).strip()

            # =====================================================
            # VALID PROSPECT
            # =====================================================
            # The classification service is authoritative for semantic
            # exclusions. In particular, preserve skip_post=True from the
            # classifier instead of deriving it only from competition.
            # This prevents a classifier decision such as mode=skip from
            # being accidentally converted back into a valid prospect.

            skip_post = bool(
                classification.get("skip_post")
                or is_competitor
                or classification.get("is_blacklisted")
            )

            if competitor_relation == "PERSONAL_PROFILE":
                skip_post = True

            if profile_classification == "COMMON_PERSON":
                skip_post = True

            if competitor_relation == "UNRELATED_BUSINESS":
                skip_post = True

            # A geographically restricted campaign only admits a verified
            # location match. The classifier service normally enforces this,
            # but keeping the guard here makes the task safe against legacy
            # or malformed classifier responses.
            strategy = campaign.get("strategy_snapshot") or {}
            if not isinstance(strategy, dict):
                strategy = {}
            locations = campaign.get("locations")
            if locations is None:
                locations = strategy.get("locations")
            if not isinstance(locations, list):
                locations = [locations] if locations else []
            locations = [str(x).strip() for x in locations if str(x or "").strip()]
            if locations and classification.get("location_match") is not True:
                skip_post = True

            # =====================================================
            # SCORE COMPATIBLE CON EL FLUJO EXISTENTE
            # =====================================================
            #
            # El flujo actual utiliza qualification_score con:
            #
            #     MIN_SCORE_TO_ENGAGE = 6
            #
            # El nuevo clasificador entrega commercial_intent_score
            # de 0-100.
            #
            # Lo convertimos a 0-10 para mantener compatibilidad.
            #

            qualification_score = int(round(commercial_intent_score / 10.0))

            if skip_post:
                qualification_score = 0

            is_valid = not skip_post

            # =====================================================
            # REASONS
            # =====================================================

            if blacklist_reason:
                qualification_reason = blacklist_reason

            elif classification_evidence:
                qualification_reason = "; ".join(
                    str(item).strip()
                    for item in classification_evidence
                    if str(item).strip()
                )

            else:
                qualification_reason = (
                    f"Perfil={profile_classification}; "
                    f"vertical={business_vertical}; "
                    f"competitor_relation={competitor_relation}; "
                    f"commercial_intent={commercial_intent_score}"
                )

            post_reason = qualification_reason

            # =====================================================
            # RESULTADO NORMALIZADO
            # =====================================================

            result = {
                # -------------------------------------------------
                # Campos legacy utilizados por el flujo existente
                # -------------------------------------------------
                "is_valid": is_valid,
                "industry_target": industry_target,
                "industry_detected": industry_detected,
                "qualification_score": qualification_score,
                "qualification_reason": qualification_reason,
                "qualification_decision": str(classification.get("qualification_decision") or ("DISCARDED" if skip_post else ("QUALIFIED" if qualification_score >= 6 else "REVIEW"))),
                "engageable": bool(classification.get("engageable")) if "engageable" in classification else bool(is_valid and qualification_score >= 6),
                "post_reason": post_reason,

                # -------------------------------------------------
                # Multi-industry / commercial classification
                # -------------------------------------------------
                "location_match": classification.get("location_match"),
                "location_confidence": str(
                    classification.get("location_confidence") or "low"
                ).strip().lower(),
                "location_evidence": (
                    classification.get("location_evidence")
                    if isinstance(classification.get("location_evidence"), list)
                    else []
                ),
                "skip_post": skip_post,

                "mode": (
                    "skip"
                    if skip_post
                    else str(
                        classification.get("mode")
                        or "normal_prospecting"
                    ).strip().lower()
                ),

                "selected_service": str(
                    classification.get("selected_service")
                    or ""
                ).strip(),

                "b2b_target_type": str(
                    classification.get("b2b_target_type")
                    or ""
                ).strip(),

                "b2b_angle": str(
                    classification.get("b2b_angle")
                    or ""
                ).strip(),

                "b2b_confidence": str(
                    classification.get("b2b_confidence")
                    or "low"
                ).strip().lower(),

                "request_directness": str(
                    classification.get("request_directness")
                    or ("none" if skip_post else "indirect")
                ).strip().lower(),

                "service_match_reason": str(
                    classification.get("service_match_reason")
                    or qualification_reason
                ).strip(),

                "comment": str(
                    classification.get("comment")
                    or ""
                ).strip(),

                # -------------------------------------------------
                # Nuevos campos del Classification Service
                # -------------------------------------------------
                "competitor_score": competitor_score,
                "is_competitor": is_competitor,
                "is_blacklisted": bool(
                    classification.get("is_blacklisted")
                ),
                "blacklist_reason": blacklist_reason,

                "profile_classification": profile_classification,
                "business_role": business_role,
                "business_vertical": business_vertical,
                "competitor_relation": competitor_relation,

                "commercial_intent_score": commercial_intent_score,
                "classification_confidence": classification_confidence,
                "classification_evidence": classification_evidence,
            }

            self.log.info(
                "[prospecting] candidate classification final | "
                "username=%s | valid=%s | skip=%s | "
                "competitor=%s | relation=%s | vertical=%s | "
                "intent=%s | qualification_score=%s",
                profile_context.get("username"),
                result["is_valid"],
                result["skip_post"],
                result["is_competitor"],
                result["competitor_relation"],
                result["business_vertical"],
                result["commercial_intent_score"],
                result["qualification_score"],
            )

            return result

        except Exception as e:
            self.log.exception(
                "[prospecting] error en _qualify_candidate_with_ai: %r",
                e,
            )

            return {
                "is_valid": False,
                "industry_detected": "unknown",
                "qualification_score": 0,
                "qualification_reason": f"Error IA: {e}",
                "post_reason": "Error clasificando",

                "skip_post": True,
                "mode": "skip",
                "selected_service": "",
                "b2b_target_type": "",
                "b2b_angle": "",
                "b2b_confidence": "low",
                "request_directness": "none",
                "service_match_reason": "",
                "comment": "",

                "competitor_score": 0,
                "is_competitor": False,
                "is_blacklisted": False,
                "blacklist_reason": "",
                "profile_classification": "UNKNOWN",
                "business_role": "UNKNOWN",
                "business_vertical": "UNKNOWN",
                "competitor_relation": "UNKNOWN",
                "commercial_intent_score": 0,
                "classification_confidence": 0,
                "classification_evidence": [],
            }
    def _extract_ai_qualification_json(self, raw_response):
        try:
            data = raw_response

            if isinstance(data, dict):
                if "response" in data and isinstance(data["response"], str):
                    content = data["response"].strip()
                else:
                    content = data
            else:
                content = str(data).strip()

            if isinstance(content, dict):
                parsed = content
            else:
                text = str(content).strip()

                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "").strip()

                start = text.find("{")
                end = text.rfind("}")

                if start != -1 and end != -1 and end > start:
                    text = text[start:end + 1]

                parsed = json.loads(text)

            if not isinstance(parsed, dict):
                return None

            return parsed

        except Exception as e:
            self.log.warning("No se pudo parsear JSON de clasificación IA: %r", e)
            return None

    # =========================================================
    # SAVE
    # =========================================================
    def _save_discovered_candidate(
        self,
        post_context: dict,
        profile_context: dict,
        qualification: dict,
    ) -> dict:
        try:
            campaign_id = self.current_campaign["id"]

            social_media_account_id = self.current_social_media_account_id

            if not social_media_account_id:
                social_media_account = self._get_social_media_account()
                social_media_account_id = social_media_account.get("id")

            decision = str(qualification.get("qualification_decision") or "").strip().upper()
            if decision == "DISCARDED" or not qualification.get("is_valid"):
                prospect_status = "discarded"
                post_status = "discarded"
            elif decision == "QUALIFIED" and qualification.get("engageable"):
                prospect_status = "qualified"
                post_status = "relevant"
            else:
                # REVIEW is a valid saved prospect, but not engagement-ready.
                prospect_status = "new"
                post_status = "relevant"

            self.log.info(
                "[prospecting] saving_candidate | campaign_id=%s | account_id=%s | prospect_status=%s | post_status=%s | qualification=%s",
                campaign_id,
                social_media_account_id,
                prospect_status,
                post_status,
                self._shorten_for_log(qualification),
            )

            ok_prospect, prospect, created_prospect = self.prospecting_api.get_or_create_prospect(
                campaign_id=campaign_id,
                platform="instagram",
                username=profile_context["username"],
                profile_url=profile_context["profile_url"],
                display_name=profile_context.get("display_name", ""),
                bio=profile_context.get("bio", ""),
                industry_detected=qualification.get("industry_detected", ""),
                source_type="hashtag",
                source_value=self.current_search_term,
                status=prospect_status,
                qualification_score=qualification.get("qualification_score", 0),
                qualification_reason=qualification.get("qualification_reason", ""),
            )

            self.log.info(
                "[prospecting] save_prospect_ok=%s | created=%s | prospect=%s",
                ok_prospect,
                created_prospect,
                self._shorten_for_log(prospect),
            )

            if not ok_prospect:
                self.log.warning("No se pudo guardar prospect: %s", prospect)
                return {"ok": False, "error": prospect}

            # Best-effort persistence of the richer classifier contract. The
            # backend used by older installations may reject unknown fields;
            # ProspectingAPI handles that case without breaking the legacy save.
            metadata = {
                "industry_target": qualification.get("industry_target"),
                "industry_detected": qualification.get("industry_detected"),
                "location_match": qualification.get("location_match"),
                "location_confidence": qualification.get("location_confidence"),
                "location_evidence": qualification.get("location_evidence") or [],
                "profile_classification": qualification.get("profile_classification"),
                "business_role": qualification.get("business_role"),
                "business_vertical": qualification.get("business_vertical"),
                "competitor_relation": qualification.get("competitor_relation"),
                "commercial_intent_score": qualification.get("commercial_intent_score"),
                "classification_confidence": qualification.get("classification_confidence"),
                "qualification_score": qualification.get("qualification_score"),
                "qualification_decision": qualification.get("qualification_decision"),
                "engageable": qualification.get("engageable"),
            }
            metadata = {k: v for k, v in metadata.items() if v is not None}
            if metadata:
                self.prospecting_api.update_prospect_metadata(prospect.get("id"), metadata)

            ok_post, prospect_post, created_post = self.prospecting_api.get_or_create_prospect_post(
                prospect_id=prospect["id"],
                post_url=post_context["post_url"],
                post_type=post_context.get("post_type", "post"),
                caption_text=(post_context.get("caption_text")or post_context.get("text_context")or ""),
                analysis_status="analyzed",
                is_relevant=qualification["is_valid"],
                analysis_reason=qualification.get("post_reason", ""),
                status=post_status,
            )

            self.log.info(
                "[prospecting] save_post_ok=%s | created=%s | prospect_post=%s",
                ok_post,
                created_post,
                self._shorten_for_log(prospect_post),
            )

            if not ok_post:
                self.log.warning("No se pudo guardar prospect_post: %s", prospect_post)
                return {"ok": False, "error": prospect_post, "prospect": prospect}

            ok_interaction, interaction = self.prospecting_api.create_prospect_interaction(
                prospect_id=prospect["id"],
                prospect_post_id=prospect_post["id"],
                social_media_account_id=social_media_account_id,
                interaction_type="analyzed",
                direction="outbound",
                content_text=qualification.get("qualification_reason", ""),
                status="success",
            )

            self.log.info(
                "[prospecting] save_interaction_ok=%s | interaction=%s",
                ok_interaction,
                self._shorten_for_log(interaction),
            )

            self.log.info(
                "Prospect guardado | username=%s | valid=%s | score=%s | account_id=%s",
                profile_context["username"],
                qualification["is_valid"],
                qualification.get("qualification_score", 0),
                social_media_account_id,
            )

            return {
                "ok": True,
                "prospect": prospect,
                "prospect_post": prospect_post,
                "created_prospect": created_prospect,
                "created_post": created_post,
            }

        except Exception as e:
            self.log.warning("Error guardando candidato descubierto: %r", e)
            return {"ok": False, "error": str(e)}

    # =========================================================
    # HELPERS
    # =========================================================
    def _get_social_media_account(self) -> dict:
        value = self.data.get("social_media_account") or {}
        return value if isinstance(value, dict) else {}

    def _get_bot_personality_id(self) -> Optional[int]:
        try:
            social_media_account = self._get_social_media_account()

            bot_personality = social_media_account.get("bot_personality")

            if isinstance(bot_personality, dict):
                bot_personality_id = bot_personality.get("id")

                if bot_personality_id:
                    return int(bot_personality_id)

            bot_personality_id = social_media_account.get("bot_personality_id")

            if bot_personality_id:
                return int(bot_personality_id)

            return None

        except Exception:
            return None

    def _open_url(self, url: str) -> None:
        """
        Se conserva porque algunos mixins heredados pueden llamarlo.
        """
        self.profile_service.open_url(url)

    def _safe_float(self, value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _safe_int(self, value, default=0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _shorten_for_log(self, value, max_len: int = 1200):
        try:
            text = value

            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False, default=str)

            text = text.replace("\\n", " ").replace("\n", " ").strip()

            if len(text) > max_len:
                return text[:max_len] + "...[truncated]"

            return text

        except Exception:
            return str(value)