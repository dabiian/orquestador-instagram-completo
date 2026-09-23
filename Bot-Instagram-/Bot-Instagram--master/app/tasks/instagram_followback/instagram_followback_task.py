import logging
import random
from typing import Optional

from .instagram_followback_navigation import InstagramFollowbackNavigationMixin
from .instagram_followback_comments import InstagramFollowbackCommentsMixin
from .instagram_followback_profiles import InstagramFollowbackProfilesMixin
from .instagram_followback_text import InstagramFollowbackTextMixin
from .instagram_followback_js import InstagramFollowbackJSMixin

from app.services.instagram_post_interaction_service import InstagramPostInteractionService
from app.services.instagram_comment_generation_service import InstagramCommentGenerationService
from app.services.instagram_post_media_service import InstagramPostMediaService


class InstagramFollowbackTask(
    InstagramFollowbackNavigationMixin,
    InstagramFollowbackCommentsMixin,
    InstagramFollowbackProfilesMixin,
    InstagramFollowbackTextMixin,
    InstagramFollowbackJSMixin,
):
    def __init__(self, browser, ai_api, account_api, data: dict):
        self.browser = browser
        self.ai_api = ai_api
        self.account_api = account_api
        self.data = data or {}
        self.log = logging.getLogger(self.__class__.__name__)
        self.current_post_url = None
        self.post_media_service = InstagramPostMediaService(
            browser=self.browser,
            ai_api=self.ai_api,
            logger=self.log,
        )
        self.comment_generation_service = InstagramCommentGenerationService(
            data=self.data,
            account_api=self.account_api,
            ai_api=self.ai_api,
            post_media_service=self.post_media_service,
            logger=self.log,
        )
        self.post_interaction_service = InstagramPostInteractionService(
            browser=self.browser,
            logger=self.log,
        )
    def execute(self) -> bool:
        try:
            self.log.info("Starting InstagramFollowbackTask.")
            self.browser.time_sleep(2)

            if not self._open_search_button():
                self.log.warning("No se pudo abrir el botón de búsqueda.")
                return False

            if not self._type_search_term():
                self.log.warning("No se pudo escribir el término de búsqueda.")
                return False

            result_hrefs = self._collect_hashtag_result_hrefs()
            if not result_hrefs:
                self.log.warning("No se encontraron resultados del hashtag.")
                return False

            target_total = random.randint(10, 15)
            completed_total = 0
            processed_profiles = set()

            print(f"[followback] objetivo total de perfiles a procesar: {target_total}")
            print(f"[followback] resultados de hashtag recolectados: {len(result_hrefs)}")

            for result_index, hashtag_href in enumerate(result_hrefs, start=1):
                if completed_total >= target_total:
                    break

                try:
                    print(f"[followback] entrando al resultado #{result_index}: {hashtag_href}")

                    if not self._open_hashtag_result_by_href(hashtag_href):
                        self.log.warning("No se pudo abrir el resultado #%s", result_index)
                        continue

                    self.browser.time_sleep(4)

                    restantes = target_total - completed_total
                    hechos = self._find_valid_followback_post(
                        max_attempts=12,
                        target_actions=restantes,
                        processed_profiles=processed_profiles,
                        result_href=hashtag_href,
                    )

                    completed_total += hechos

                    self.log.info(
                        "Resultado #%s completado | acumulado=%s/%s | href=%s",
                        result_index,
                        completed_total,
                        target_total,
                        hashtag_href,
                    )

                except Exception as e:
                    self.log.warning(
                        "Error procesando resultado de búsqueda #%s: %r",
                        result_index,
                        e,
                    )
                    continue

            return completed_total > 0

        except Exception as e:
            self.log.exception("Error in InstagramFollowbackTask: %s", e)
            return False


    def _find_valid_followback_post(
        self,
        max_attempts: int = 6,
        target_actions: int = 1,
        processed_profiles: Optional[set] = None,
        result_href: str = "",
    ) -> int:
        tried_hrefs = set()

        if processed_profiles is None:
            processed_profiles = set()

        completed = 0

        for attempt in range(1, max_attempts + 1):
            if completed >= target_actions:
                break

            try:
                print(f"[followback] validando publicación candidata {attempt}/{max_attempts}")

                opened_href = self._open_next_post_from_hashtag_grid(excluded_hrefs=tried_hrefs)
                if not opened_href:
                    self.log.warning("No se pudo abrir una nueva publicación candidata.")
                    break

                tried_hrefs.add(opened_href)
                print(f"[followback] publicación abierta: {opened_href}")

                self.browser.time_sleep(4)

                # Comentarios visibles: ahora son opcionales para poder comentar el post
                comments = self._get_visible_comments() or []
                comments_texts = self._get_visible_comments_texts(comments) if comments else []

                is_valid_by_comments = False
                if comments_texts:
                    is_valid_by_comments = self._validate_post_by_comments(
                        comments_texts,
                        min_matches=2,
                        min_comments_to_check=10,
                        max_comments_to_check=12,
                    )

                image_validation = self.post_media_service.validate_current_post_followback_image()
                is_valid_by_image = bool(image_validation.get("is_followback_image", False))

                print(
                    f"[followback] validación post | "
                    f"comments={is_valid_by_comments} | "
                    f"image={is_valid_by_image} | "
                    f"media_type={image_validation.get('media_type')} | "
                    f"reason={image_validation.get('reason')}"
                )

                is_valid_post = is_valid_by_comments or is_valid_by_image

                if not is_valid_post:
                    print(
                        f"[followback] publicación descartada | "
                        f"comments={is_valid_by_comments} | "
                        f"image={is_valid_by_image} | href={opened_href}"
                    )
                    self._return_to_result_grid(result_href)
                    continue

                # 2) Luego seguir con el flujo viejo de expandir comentarios + seguir + responder
                candidate_comments = self._get_expanded_comments_for_candidates(
                    max_rounds=6,
                    min_comments_goal=35,
                )

                if not candidate_comments:
                    candidate_comments = comments

                already_commented_by_me = self._already_commented_current_post(candidate_comments)

                if already_commented_by_me:
                    print("[followback-post] ya había comentario mío en este post, se omite nuevo comentario")
                else:
                    post_context = self.post_media_service.get_current_post_context()
                    print(f"[followback-post] post_context={post_context}")

                    comment_ok = self._comment_current_valid_post()
                    if comment_ok:
                        print(f"[followback-post] publicación comentada correctamente | href={opened_href}")
                    else:
                        print(f"[followback-post] no se pudo comentar la publicación: {opened_href}")

                unique_candidates = []
                seen_profiles = set()

                for comment in candidate_comments:
                    profile_href = (comment.get("profile_href") or "").strip().replace(" ", "")
                    comment_username = str(comment.get("username") or "").strip().lower()

                    if not profile_href:
                        continue
                    if comment.get("username_element") is None:
                        continue
                    if comment.get("element") is None:
                        continue
                    if comment.get("has_reply_button") is not True:
                        continue
                    if profile_href in processed_profiles:
                        continue
                    if profile_href in seen_profiles:
                        continue

                    my_username = str(
                        (self.data.get("social_media_account") or {}).get("username") or ""
                    ).strip().lower()

                    if my_username and comment_username == my_username:
                        continue

                    seen_profiles.add(profile_href)
                    unique_candidates.append(comment)

                print(
                    f"[followback] candidatos estructurales en el post: {len(unique_candidates)} | "
                    f"comentarios_analisis={len(comments)} | "
                    f"comentarios_candidatos={len(candidate_comments)}"
                )

                # Si no hay candidatos, igual ya intentó comentar el post
                if not unique_candidates:
                    self._return_to_result_grid(result_href)
                    self.browser.time_sleep(1.5)
                    continue

                random.shuffle(unique_candidates)

                for selected_comment in unique_candidates:
                    if completed >= target_actions:
                        break

                    profile_href = (selected_comment.get("profile_href") or "").strip().replace(" ", "")
                    reply_href = (selected_comment.get("permalink") or "").strip() or opened_href

                    print(
                        f"[followback] procesando candidato | "
                        f"profile={profile_href} | reply_href={reply_href}"
                    )

                    follow_status = self._open_profile_follow_and_return(
                        comment=selected_comment,
                        post_href=opened_href,
                    )

                    if follow_status == "already_following":
                        print(f"[followback] ya se seguía el perfil, no se comenta: {profile_href}")
                        processed_profiles.add(profile_href)
                        self.browser.time_sleep(1.0)
                        continue

                    if follow_status == "followed":
                        reply_ok = self._reply_to_followback_comment(
                            original_comment=selected_comment,
                            post_href=reply_href,
                        )

                        processed_profiles.add(profile_href)

                        if reply_ok:
                            completed += 1
                            print(f"[followback] perfil completado: {profile_href} | total={completed}")
                        else:
                            print(f"[followback] se siguió el perfil, pero no se pudo responder: {profile_href}")

                        if completed >= target_actions:
                            break

                        self.browser.time_sleep(1.5)
                        continue

                    print(f"[followback] no se pudo seguir perfil: {profile_href}")
                    self.browser.time_sleep(1.0)

                self._return_to_result_grid(result_href)

            except Exception as e:
                self.log.warning("Error validando publicación candidata: %r", e)
                self._return_to_result_grid(result_href)

        return completed
    
    def _comment_current_valid_post(self) -> bool:
        try:
            ok_comment_ai, comment_text = (
                self.comment_generation_service.generate_comment_from_current_post_context_safe(
                    category="comentario_publicacion_seguidor",
                )
            )

            if not ok_comment_ai or not comment_text:
                self.log.warning("No se pudo generar comentario contextual para el post.")
                return False

            print(f"[followback-post] comentario generado: {comment_text}")

            ok_comment = self.post_interaction_service.comment_current_post(comment_text)
            if not ok_comment:
                self.log.warning("No se pudo comentar la publicación actual.")
                return False

            self.browser.time_sleep(random.randint(1, 2))

            like_state = self.post_interaction_service.has_post_like()

            if like_state is None:
                self.log.warning("No se pudo determinar si la publicación ya tenía like.")
                return True

            if like_state is True:
                print("[followback-post] la publicación ya tenía like")
                return True

            ok_like = self.post_interaction_service.like_current_post()
            if ok_like:
                print("[followback-post] like aplicado correctamente al post")
            else:
                self.log.warning("El comentario se hizo, pero no se pudo dar like al post.")

            self.browser.time_sleep(random.randint(1, 2))
            return True

        except Exception as e:
            self.log.warning("Error comentando publicación válida: %r", e)
            return False


    def _get_my_instagram_username(self) -> str:
        try:
            social_media_account = self.data.get("social_media_account") or {}

            username = str(
                social_media_account.get("username") or ""
            ).strip().lower().replace("@", "")

            if username:
                return username

            username = str(
                (social_media_account.get("other_credentials") or {}).get("User") or ""
            ).strip().lower().replace("@", "")

            if username:
                return username

            return ""
        except Exception:
            return ""


    def _already_commented_current_post(self, comments: list[dict]) -> bool:
        my_username = self._get_my_instagram_username()
        print(f"[followback-post] my_username_detectado={my_username}")

        if not my_username:
            return False

        expected_profile_href = f"https://www.instagram.com/{my_username}/"

        for comment in comments or []:
            comment_username = str(comment.get("username") or "").strip().lower().replace("@", "")
            comment_text = str(comment.get("text") or "").strip()
            profile_href = str(comment.get("profile_href") or "").strip().replace(" ", "")

            if not comment_text:
                continue

            if comment_username == my_username:
                print(
                    f"[followback-post] ya existe comentario mío en el post | "
                    f"username={comment_username} | text={comment_text}"
                )
                return True

            if profile_href.rstrip("/") == expected_profile_href.rstrip("/"):
                print(
                    f"[followback-post] ya existe comentario mío en el post por href | "
                    f"profile_href={profile_href} | text={comment_text}"
                )
                return True

        return False