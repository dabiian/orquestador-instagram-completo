import random

from app.core.interfaces import IBrowser, ITask
from app.utils.logger import get_logger
from app.services.instagram_profile_service import InstagramProfileService
from app.services.instagram_post_media_service import InstagramPostMediaService
from app.services.instagram_post_interaction_service import InstagramPostInteractionService
from app.services.instagram_comment_generation_service import InstagramCommentGenerationService
from app.api.prospecting_api import ProspectingAPI
from app.utils.instagram_url import _normalize_instagram_href


class InteractWithOwnerLatestPostTask(ITask):
    """
    Flujo:
    1. Obtener campaña de prospectación activa vinculada a la cuenta.
    2. Leer owner_instagram_profile_url desde esa campaña.
    3. Abrir perfil del owner/campaña.
    4. Si no lo seguimos, seguirlo.
    5. Leer publicaciones del perfil.
    6. Ir de la más reciente hacia abajo.
    7. Si una publicación ya tiene like, saltarla.
    8. Si no tiene like:
       - generar comentario contextual por imagen/caption/perfil
       - comentar
       - dar like
       - compartir
    """

    def __init__(self, browser: IBrowser, data: dict, account_api, ai_api):
        self.browser = browser
        self.data = data or {}
        self.account_api = account_api
        self.ai_api = ai_api
        self.log = get_logger(self.__class__.__name__)

        self.prospecting_api = ProspectingAPI()

        self.profile_service = InstagramProfileService(
            browser=self.browser,
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

    def execute(self) -> str:
        try:
            owner_profile_url = self._get_campaign_owner_instagram_url()

            if not owner_profile_url:
                return "✗ No se encontró owner_instagram_profile_url en la campaña de prospectación activa"

            follow_status = self.profile_service.ensure_follow_profile(owner_profile_url)

            if follow_status == "error":
                return f"✗ No se pudo validar/seguir el perfil de campaña: {owner_profile_url}"

            if follow_status == "already_following":
                print(f"[owner-task] ya se seguía el perfil de campaña: {owner_profile_url}")
            else:
                print(f"[owner-task] perfil de campaña seguido correctamente: {owner_profile_url}")

            profile_context = self.post_media_service.get_current_profile_description_context()
            print(f"[owner-task] profile_context={profile_context}")

            self.browser.time_sleep(random.randint(3, 5))

            result = self._process_owner_posts(
                max_scrolls=4,
                profile_context=profile_context,
            )

            if str(result).startswith("✗"):
                return (
                    f"✗ Perfil de campaña procesado sin interacción completa | "
                    f"{owner_profile_url} | {result}"
                )

            return f"✓ Perfil de campaña procesado correctamente | {owner_profile_url} | {result}"

        except Exception as e:
            self.log.error("Error en InteractWithOwnerLatestPostTask: %r", e)
            return f"✗ Error en InteractWithOwnerLatestPostTask: {repr(e)}"

    # =========================================================
    # CAMPAIGN URL RESOLUTION
    # =========================================================
    def _get_campaign_owner_instagram_url(self) -> str:
        """
        Prioridad:
        1. custom_task.owner_instagram_profile_url / instagram_profile_url
        2. campaign/prospecting_campaign en payload
        3. active campaign desde ProspectingAPI usando social_media_account_id
        """
        try:
            custom_task = self._get_custom_task()

            direct_url = str(
                custom_task.get("owner_instagram_profile_url")
                or custom_task.get("instagram_profile_url")
                or custom_task.get("profile_url")
                or ""
            ).strip()

            if direct_url:
                return self._normalize_campaign_instagram_url(
                    direct_url,
                    source="custom_task",
                )

            campaign = self._get_campaign_from_payload()

            url_from_payload = self._extract_owner_url_from_campaign(campaign)

            if url_from_payload:
                return self._normalize_campaign_instagram_url(
                    url_from_payload,
                    source="payload_campaign",
                )

            social_media_account = self._get_social_media_account()
            account_id = social_media_account.get("id")

            if not account_id:
                self.log.warning(
                    "[owner-task] no hay social_media_account.id para buscar campaña activa."
                )
                return ""

            ok_campaign, active_campaign = self.prospecting_api.get_active_campaign(
                social_media_account_id=account_id,
                platform="instagram",
            )

            self.log.info(
                "[owner-task] active campaign lookup | ok=%s | campaign=%s",
                ok_campaign,
                self._shorten_for_log(active_campaign),
            )

            if not ok_campaign or not isinstance(active_campaign, dict):
                self.log.warning(
                    "[owner-task] no se encontró campaña activa para account_id=%s",
                    account_id,
                )
                return ""

            url_from_api = self._extract_owner_url_from_campaign(active_campaign)

            if not url_from_api:
                self.log.warning(
                    "[owner-task] campaña activa sin owner_instagram_profile_url | campaign=%s",
                    self._shorten_for_log(active_campaign),
                )
                return ""

            return self._normalize_campaign_instagram_url(
                url_from_api,
                source="active_campaign",
            )

        except Exception as e:
            self.log.warning(
                "[owner-task] error obteniendo owner_instagram_profile_url desde campaña: %r",
                e,
            )
            return ""

    def _extract_owner_url_from_campaign(self, campaign: dict) -> str:
        if not isinstance(campaign, dict):
            return ""

        return str(
            campaign.get("owner_instagram_profile_url")
            or campaign.get("instagram_profile_url")
            or campaign.get("profile_instagram_url")
            or campaign.get("owner_profile_url")
            or ""
        ).strip()

    def _normalize_campaign_instagram_url(self, value: str, source: str = "") -> str:
        try:
            value = str(value or "").strip()

            if not value:
                return ""

            if value.startswith("@"):
                value = f"https://www.instagram.com/{value.lstrip('@').strip()}/"

            elif "instagram.com" not in value:
                value = value.strip().strip("/")
                value = f"https://www.instagram.com/{value}/"

            if "instagram.com" not in value:
                self.log.warning(
                    "[owner-task] URL inválida desde %s: %s",
                    source,
                    value,
                )
                return ""

            normalized = _normalize_instagram_href(value)

            self.log.info(
                "[owner-task] owner Instagram URL detectada desde %s: %s",
                source,
                normalized,
            )

            return normalized

        except Exception as e:
            self.log.warning(
                "[owner-task] error normalizando Instagram URL desde %s: %r",
                source,
                e,
            )
            return ""

    # =========================================================
    # PROCESS POSTS
    # =========================================================
    def _process_owner_posts(self, max_scrolls=4, profile_context: dict | None = None):
        """
        Regla:
        - si el post ya tiene like, saltar al siguiente
        - si no tiene like:
            1) generar comentario contextual por imagen/caption/perfil
            2) comentar
            3) dar like
            4) compartir
        """
        post_urls = self.profile_service.collect_profile_post_urls(
            profile_url=self.browser.driver.current_url,
            limit=max(8, max_scrolls * 4),
        )

        if not post_urls:
            self.log.warning("No se encontraron publicaciones en el perfil de campaña.")
            return "✗ No se encontraron publicaciones en el perfil de campaña"

        self.log.info("Posts detectados en el perfil de campaña: %s", len(post_urls))

        already_interacted_posts = 0
        skipped_posts_due_to_error = 0

        for index, post_url in enumerate(post_urls, start=1):
            try:
                self.log.info(
                    "Revisando owner/campaign post %s/%s: %s",
                    index,
                    len(post_urls),
                    post_url,
                )

                opened = self.profile_service.open_post_url(
                    post_url=post_url,
                    sleep_seconds=random.randint(3, 5),
                )

                if not opened:
                    skipped_posts_due_to_error += 1
                    self.log.warning("No se pudo abrir el post %s", post_url)
                    continue

                like_state = self.post_interaction_service.has_post_like()

                if like_state is None:
                    skipped_posts_due_to_error += 1
                    self.log.warning(
                        "No se pudo determinar el like state de %s. Se salta seguro.",
                        post_url,
                    )
                    continue

                if like_state is True:
                    already_interacted_posts += 1
                    self.log.info("La publicación ya tenía like. Se salta.")
                    continue

                ok_comment_ai, comment_text = (
                    self.comment_generation_service.generate_comment_from_current_post_image_caption_profile_description(
                        profile_context=profile_context,
                        category="comentario_publicacion_owner",
                    )
                )

                if not ok_comment_ai or not comment_text:
                    skipped_posts_due_to_error += 1
                    self.log.warning("No se pudo generar comentario IA para %s", post_url)
                    continue

                print(f"[owner-task] comentario generado: {comment_text}")

                ok_comment = self.post_interaction_service.comment_current_post(comment_text)

                if not ok_comment:
                    skipped_posts_due_to_error += 1
                    self.log.warning("Falló el comentario en %s", post_url)
                    continue

                self.browser.time_sleep(random.randint(1, 2))

                ok_like = self.post_interaction_service.like_current_post()

                if not ok_like:
                    skipped_posts_due_to_error += 1
                    self.log.warning(
                        "El comentario salió bien pero el like falló en %s",
                        post_url,
                    )
                    continue

                self.browser.time_sleep(random.randint(1, 2))

                ok_share = self.post_interaction_service.share_current_post()

                if ok_share:
                    return f"✓ Comment + like + share completed on campaign owner post: {post_url}"

                skipped_posts_due_to_error += 1
                self.log.warning(
                    "Comentario y like salieron bien pero share falló en %s",
                    post_url,
                )

            except Exception as e:
                skipped_posts_due_to_error += 1
                self.log.warning("Error revisando owner/campaign post %s: %r", post_url, e)
                continue

        if already_interacted_posts == len(post_urls):
            return "✗ Todas las publicaciones del perfil de campaña ya tenían like"

        if skipped_posts_due_to_error > 0:
            return "✗ No se encontró publicación segura donde comentar + like + share"

        return "✗ No se pudo procesar ninguna publicación válida del perfil de campaña"

    # =========================================================
    # PAYLOAD HELPERS
    # =========================================================
    def _get_custom_task(self) -> dict:
        value = self.data.get("custom_task") or {}
        return value if isinstance(value, dict) else {}

    def _get_social_media_account(self) -> dict:
        value = self.data.get("social_media_account") or {}
        return value if isinstance(value, dict) else {}

    def _get_campaign_from_payload(self) -> dict:
        candidates = [
            self.data.get("prospecting_campaign"),
            self.data.get("campaign"),
            self.data.get("active_campaign"),
            (self.data.get("task") or {}).get("campaign")
            if isinstance(self.data.get("task"), dict)
            else None,
            (self.data.get("social_media_account") or {}).get("prospecting_campaign")
            if isinstance(self.data.get("social_media_account"), dict)
            else None,
            (self.data.get("social_media_account") or {}).get("campaign")
            if isinstance(self.data.get("social_media_account"), dict)
            else None,
        ]

        for candidate in candidates:
            if isinstance(candidate, dict):
                return candidate

        return {}

    def _shorten_for_log(self, value, max_len: int = 1200):
        try:
            import json

            text = value

            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False, default=str)

            text = text.replace("\\n", " ").replace("\n", " ").strip()

            if len(text) > max_len:
                return text[:max_len] + "...[truncated]"

            return text

        except Exception:
            return str(value)