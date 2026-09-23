import json
import random
import re
import unicodedata

from app.utils.logger import get_logger
from app.utils.instagram_url import _normalize_instagram_href
from app.services.instagram_post_interaction_service import InstagramPostInteractionService
from app.services.instagram_curated_source_resolver import InstagramCuratedSourceResolver
from app.services.instagram_profile_service import InstagramProfileService
from app.tasks.instagram_followback.instagram_followback_navigation import (
    InstagramFollowbackNavigationMixin,
)


class ShareInstagramCuratedPostTask(InstagramFollowbackNavigationMixin):
    """
    Busca publicaciones existentes y las comparte.

    Modos soportados:
    - phrase
    - meme
    - local_news
    - world_news

    Flujo:
    1. Resolver fuentes dinámicas según content_mode, idioma y ubicación.
    2. Buscar posts por hashtag o cuenta.
    3. Abrir publicación candidata.
    4. Evitar post propio.
    5. Validar idioma del caption/texto visible:
       - filtro local primero
       - IA solo si queda dudoso
    6. Revisar si ya tiene like.
       - Si ya tiene like: saltar al siguiente post.
       - Si no tiene like: dar like.
    7. Compartir.
    8. No guarda memoria en BD.

    Esta tarea NO genera contenido con IA.
    Esta tarea NO crea imágenes.
    Esta tarea NO crea captions.
    """

    MAX_POSTS_TO_CHECK_DEFAULT = 8
    MAX_SOURCES_TO_TRY_DEFAULT = 4

    def __init__(self, browser, ai_api, account_api, data: dict):
        self.browser = browser
        self.ai_api = ai_api
        self.account_api = account_api
        self.data = data or {}
        self.log = get_logger(self.__class__.__name__)

        self.source_resolver = InstagramCuratedSourceResolver()

        self.profile_service = InstagramProfileService(
            browser=self.browser,
            logger=self.log,
        )

        self.post_interaction_service = InstagramPostInteractionService(
            browser=self.browser,
            logger=self.log,
        )

        self.current_search_term = ""
        self.current_content_mode = ""
        self.current_source_type = ""
        self.current_language = ""
        self.current_location = ""

    # =========================================================
    # ENTRYPOINT
    # =========================================================
    def execute(self) -> bool:
        try:
            custom_task = self._get_custom_task()

            resolved = self.source_resolver.resolve(data=self.data)

            content_mode = str(resolved.get("content_mode") or "").strip()
            language = str(resolved.get("language") or "").strip()
            location = str(resolved.get("location") or "").strip()
            sources = resolved.get("sources") or []

            self.current_content_mode = content_mode
            self.current_language = language
            self.current_location = location

            max_posts_to_check = self._safe_int(
                custom_task.get("max_posts_to_check"),
                self.MAX_POSTS_TO_CHECK_DEFAULT,
            )

            max_sources_to_try = self._safe_int(
                custom_task.get("max_sources_to_try"),
                self.MAX_SOURCES_TO_TRY_DEFAULT,
            )

            self.log.info(
                "[curated_share] iniciando | mode=%s | language=%s | location=%s | origin=%s | max_posts=%s | max_sources=%s",
                content_mode,
                language,
                location,
                resolved.get("source_origin"),
                max_posts_to_check,
                max_sources_to_try,
            )

            if content_mode not in self.source_resolver.CONTENT_MODES:
                self.log.warning(
                    "[curated_share] content_mode inválido: %s",
                    content_mode,
                )
                return False

            if not sources:
                self.log.warning(
                    "[curated_share] no se encontraron fuentes para mode=%s",
                    content_mode,
                )
                return False

            self.log.info(
                "[curated_share] fuentes resueltas | mode=%s | sources=%s",
                content_mode,
                sources,
            )

            sources_to_try = sources[:max_sources_to_try]

            for source in sources_to_try:
                source_type = str(source.get("type") or "").strip().lower()
                source_value = str(source.get("value") or "").strip()

                if not source_type or not source_value:
                    continue

                self.current_source_type = source_type
                self.current_search_term = source_value

                self.log.info(
                    "[curated_share] probando fuente | type=%s | value=%s | mode=%s | language=%s",
                    source_type,
                    source_value,
                    content_mode,
                    language,
                )

                if source_type == "hashtag":
                    shared = self._try_share_from_hashtag(
                        hashtag=source_value,
                        max_posts_to_check=max_posts_to_check,
                    )

                elif source_type == "account":
                    shared = self._try_share_from_account(
                        account_username=source_value,
                        max_posts_to_check=max_posts_to_check,
                    )

                else:
                    self.log.warning(
                        "[curated_share] source_type no soportado: %s",
                        source_type,
                    )
                    shared = False

                if shared:
                    self.log.info(
                        "[curated_share] publicación compartida correctamente | mode=%s | source=%s:%s",
                        content_mode,
                        source_type,
                        source_value,
                    )
                    return True

            self.log.warning(
                "[curated_share] no se pudo compartir ninguna publicación válida | mode=%s",
                content_mode,
            )
            return False

        except Exception as e:
            self.log.exception("Error en ShareInstagramCuratedPostTask: %s", e)
            return False

    # =========================================================
    # PAYLOAD
    # =========================================================
    def _get_custom_task(self) -> dict:
        value = self.data.get("custom_task") or {}
        return value if isinstance(value, dict) else {}

    def _get_social_media_account(self) -> dict:
        value = self.data.get("social_media_account") or {}
        return value if isinstance(value, dict) else {}

    def _get_bot_personality(self) -> dict:
        social_media_account = self._get_social_media_account()

        value = (
            social_media_account.get("bot_personality")
            or self.data.get("bot_personality")
            or {}
        )

        return value if isinstance(value, dict) else {}

    def _get_bot_personality_id(self):
        try:
            social_media_account = self._get_social_media_account()
            bot_personality = social_media_account.get("bot_personality") or {}

            if isinstance(bot_personality, dict):
                bot_personality_id = bot_personality.get("id")
                if bot_personality_id:
                    return int(bot_personality_id)

            bot_personality_id = social_media_account.get("bot_personality_id")
            if bot_personality_id:
                return int(bot_personality_id)

            bot_personality = self.data.get("bot_personality") or {}
            if isinstance(bot_personality, dict):
                bot_personality_id = bot_personality.get("id")
                if bot_personality_id:
                    return int(bot_personality_id)

            return None

        except Exception:
            return None

    def _get_own_username(self) -> str:
        try:
            social_media_account = self._get_social_media_account()
            credentials = social_media_account.get("other_credentials") or {}

            username = (
                credentials.get("User")
                or credentials.get("user")
                or credentials.get("username")
                or ""
            )

            return str(username or "").strip().lower().lstrip("@")

        except Exception:
            return ""

    # =========================================================
    # HASHTAG FLOW
    # =========================================================
    def _get_search_term(self) -> str:
        """
        Lo usa InstagramFollowbackNavigationMixin._type_search_term().
        Normalmente abrimos hashtags directo por URL, pero se deja compatible.
        """
        term = str(self.current_search_term or "").strip()

        if self.current_source_type == "hashtag":
            return f"#{self._clean_hashtag(term)}"

        return term

    def _try_share_from_hashtag(
        self,
        hashtag: str,
        max_posts_to_check: int = 8,
    ) -> bool:
        try:
            hashtag = self._clean_hashtag(hashtag)

            if not hashtag:
                return False

            result_href = f"https://www.instagram.com/explore/tags/{hashtag}/"

            self.log.info(
                "[curated_share] abriendo hashtag directo | hashtag=%s | url=%s",
                hashtag,
                result_href,
            )

            if not self._open_hashtag_result_by_href(result_href):
                self.log.warning(
                    "[curated_share] no se pudo abrir hashtag: %s",
                    hashtag,
                )
                return False

            tried_hrefs = set()

            for attempt in range(1, max_posts_to_check + 1):
                opened_href = self._open_next_post_from_hashtag_grid(
                    excluded_hrefs=tried_hrefs,
                )

                if not opened_href:
                    self.log.warning(
                        "[curated_share] no se pudo abrir candidato desde hashtag=%s",
                        hashtag,
                    )
                    return False

                opened_href = _normalize_instagram_href(opened_href)
                tried_hrefs.add(opened_href)

                self.log.info(
                    "[curated_share] candidato hashtag %s/%s | href=%s",
                    attempt,
                    max_posts_to_check,
                    opened_href,
                )

                if self.profile_service.is_own_post_opened(
                    own_username=self._get_own_username()
                ):
                    self.log.info("[curated_share] post propio detectado. Se salta.")
                    self._return_to_result_grid(result_href)
                    continue

                if self._try_like_and_share_opened_post(
                    post_url=opened_href,
                    source_type="hashtag",
                    source_value=hashtag,
                ):
                    return True

                self._return_to_result_grid(result_href)
                self.browser.time_sleep(random.uniform(1.2, 2.2))

            return False

        except Exception as e:
            self.log.warning(
                "[curated_share] error compartiendo desde hashtag=%s | error=%r",
                hashtag,
                e,
            )
            return False

    # =========================================================
    # ACCOUNT FLOW
    # =========================================================
    def _try_share_from_account(
        self,
        account_username: str,
        max_posts_to_check: int = 8,
    ) -> bool:
        try:
            account_username = self._clean_account_username(account_username)

            if not account_username:
                return False

            own_username = self._get_own_username()

            if own_username and own_username == account_username.lower():
                self.log.info(
                    "[curated_share] cuenta fuente es la misma cuenta. Se salta: %s",
                    account_username,
                )
                return False

            profile_url = f"https://www.instagram.com/{account_username}/"

            self.log.info(
                "[curated_share] abriendo perfil fuente | account=%s | url=%s",
                account_username,
                profile_url,
            )

            post_urls = self.profile_service.collect_profile_post_urls(
                profile_url=profile_url,
                limit=max_posts_to_check,
            )

            if not post_urls:
                self.log.warning(
                    "[curated_share] no se encontraron posts en cuenta=%s",
                    account_username,
                )
                return False

            random.shuffle(post_urls)

            for index, post_url in enumerate(post_urls[:max_posts_to_check], start=1):
                try:
                    post_url = _normalize_instagram_href(post_url)

                    self.log.info(
                        "[curated_share] candidato cuenta %s/%s | account=%s | url=%s",
                        index,
                        max_posts_to_check,
                        account_username,
                        post_url,
                    )

                    opened = self.profile_service.open_post_url(
                        post_url=post_url,
                        sleep_seconds=random.uniform(3.0, 5.0),
                    )

                    if not opened:
                        continue

                    if self.profile_service.is_own_post_opened(
                        own_username=self._get_own_username()
                    ):
                        self.log.info("[curated_share] post propio detectado. Se salta.")
                        continue

                    if self._try_like_and_share_opened_post(
                        post_url=post_url,
                        source_type="account",
                        source_value=account_username,
                    ):
                        return True

                except Exception as e:
                    self.log.warning(
                        "[curated_share] error con candidato account=%s url=%s | error=%r",
                        account_username,
                        post_url,
                        e,
                    )
                    continue

            return False

        except Exception as e:
            self.log.warning(
                "[curated_share] error compartiendo desde cuenta=%s | error=%r",
                account_username,
                e,
            )
            return False

    # =========================================================
    # LIKE + SHARE
    # =========================================================
    def _try_like_and_share_opened_post(
        self,
        post_url: str,
        source_type: str,
        source_value: str,
    ) -> bool:
        try:
            if not self.profile_service.looks_like_post_page():
                self.log.info(
                    "[curated_share] la página actual no parece post/reel: %s",
                    post_url,
                )
                return False

            self.browser.time_sleep(random.uniform(1.5, 2.5))

            if not self._post_language_matches_account():
                self.log.info(
                    "[curated_share] post descartado por idioma | url=%s | expected_language=%s",
                    post_url,
                    self.current_language,
                )
                return False

            like_state = self.post_interaction_service.has_post_like()

            if like_state is True:
                self.log.info(
                    "[curated_share] post ya tenía like. Se salta para no repetir | url=%s",
                    post_url,
                )
                return False

            if like_state is None:
                self.log.warning(
                    "[curated_share] no se pudo determinar si el post tiene like. Se salta | url=%s",
                    post_url,
                )
                return False

            ok_like = self.post_interaction_service.like_current_post()

            if not ok_like:
                self.log.warning(
                    "[curated_share] no se pudo dar like al post. Se salta | url=%s",
                    post_url,
                )
                return False

            self.browser.time_sleep(random.uniform(1.0, 2.0))

            ok_share = self.post_interaction_service.share_current_post()

            if not ok_share:
                self.log.warning(
                    "[curated_share] share_current_post falló | url=%s",
                    post_url,
                )
                return False

            self.log.info(
                "[curated_share] post con like nuevo + share OK | url=%s | source=%s:%s | mode=%s",
                post_url,
                source_type,
                source_value,
                self.current_content_mode,
            )

            self.browser.time_sleep(random.uniform(2.0, 4.0))
            return True

        except Exception as e:
            self.log.warning(
                "[curated_share] error intentando like/share post=%s | error=%r",
                post_url,
                e,
            )
            return False

    # =========================================================
    # LANGUAGE VALIDATION
    # =========================================================
    def _extract_opened_post_text_context(self) -> str:
        return self.profile_service.extract_opened_post_text_context()

    def _post_language_matches_account(self) -> bool:
        try:
            expected_language = str(self.current_language or "").strip().lower()

            if expected_language not in {"english", "spanish"}:
                return True

            text = self._extract_opened_post_text_context()
            text_norm = self._normalize_for_language_detection(text)

            if not text_norm:
                self.log.info(
                    "[curated_share] sin texto suficiente para validar idioma; se permite continuar."
                )
                return True

            scores = self._score_language_text(text_norm)

            spanish_score = scores["spanish_score"]
            english_score = scores["english_score"]

            self.log.info(
                "[curated_share] language_check | expected=%s | spanish_score=%s | english_score=%s | text=%s",
                expected_language,
                spanish_score,
                english_score,
                text[:700],
            )

            if expected_language == "english":
                if spanish_score >= 3 and spanish_score > english_score:
                    self.log.info(
                        "[curated_share] post descartado por filtro local: español claro para cuenta inglés."
                    )
                    return False

                if english_score >= 3 and english_score > spanish_score:
                    return True

                if spanish_score >= 1 and spanish_score >= english_score:
                    return self._ai_language_matches_expected(
                        text=text,
                        expected_language=expected_language,
                        spanish_score=spanish_score,
                        english_score=english_score,
                    )

            if expected_language == "spanish":
                if english_score >= 3 and english_score > spanish_score:
                    self.log.info(
                        "[curated_share] post descartado por filtro local: inglés claro para cuenta español."
                    )
                    return False

                if spanish_score >= 3 and spanish_score > english_score:
                    return True

                if english_score >= 1 and english_score >= spanish_score:
                    return self._ai_language_matches_expected(
                        text=text,
                        expected_language=expected_language,
                        spanish_score=spanish_score,
                        english_score=english_score,
                    )

            return True

        except Exception as e:
            self.log.warning("[curated_share] error validando idioma del post: %r", e)
            return True

    def _score_language_text(self, text_norm: str) -> dict:
        spanish_score = 0
        english_score = 0

        spanish_phrases = {
            " cuando ",
            " tu amigo ",
            " tu amiga ",
            " me manda ",
            " te manda ",
            " vos ",
            " apenas ",
            " captas ",
            " palabras ",
            " en ingles ",
            " en inglés ",
            " jajaja ",
            " jajajaja ",
            " jaja ",
            " ajaja ",
            " que ",
            " porque ",
            " por que ",
            " para ",
            " pero ",
            " como ",
            " con ",
            " desde ",
            " hasta ",
            " nadie ",
            " todos ",
            " todas ",
            " gente ",
            " vida ",
            " amor ",
            " trabajo ",
            " dinero ",
            " familia ",
            " amigos ",
            " amigas ",
            " mujer ",
            " hombre ",
            " dios ",
            " esta ",
            " este ",
            " esto ",
            " esa ",
            " ese ",
            " muy ",
            " mas ",
            " tambien ",
        }

        english_phrases = {
            " when ",
            " your friend ",
            " my friend ",
            " sends me ",
            " sends you ",
            " barely ",
            " words ",
            " in english ",
            " haha ",
            " lol ",
            " the ",
            " and ",
            " you ",
            " your ",
            " this ",
            " that ",
            " because ",
            " with ",
            " for ",
            " from ",
            " what ",
            " how ",
            " people ",
            " life ",
            " work ",
            " money ",
            " friends ",
            " family ",
            " today ",
            " mood ",
            " just ",
            " like ",
            " nobody ",
            " everyone ",
            " someone ",
            " love ",
            " never ",
            " always ",
            " going ",
            " want ",
            " need ",
        }

        for marker in spanish_phrases:
            if marker in text_norm:
                spanish_score += 1

        for marker in english_phrases:
            if marker in text_norm:
                english_score += 1

        return {
            "spanish_score": spanish_score,
            "english_score": english_score,
        }

    def _ai_language_matches_expected(
        self,
        *,
        text: str,
        expected_language: str,
        spanish_score: int,
        english_score: int,
    ) -> bool:
        try:
            bot_personality_id = self._get_bot_personality_id()

            if not bot_personality_id:
                self.log.info(
                    "[curated_share] no hay bot_personality_id para validar idioma con IA. Se descarta por seguridad."
                )
                return False

            clean_text = str(text or "").strip()

            if len(clean_text) > 2000:
                clean_text = clean_text[:2000]

            user_prompt = f"""
You are validating whether an Instagram post matches the expected language of an account.

EXPECTED_LANGUAGE:
{expected_language}

LOCAL_FILTER_SCORES:
- spanish_score: {spanish_score}
- english_score: {english_score}

INSTAGRAM_POST_TEXT:
{clean_text}

TASK:
Detect the main language of the actual post content, not the Instagram UI labels.
Ignore generic Instagram interface text such as likes, comments, audio labels, dates, usernames, and emojis.
Focus on the caption, visible text, image alt text, and meaningful post text.

Return ONLY valid JSON with this exact structure:
{{
  "language": "english|spanish|mixed|unknown",
  "confidence": 0,
  "reason": "short reason"
}}

RULES:
- If the post is mainly Spanish, return "spanish".
- If the post is mainly English, return "english".
- If both languages are meaningfully present, return "mixed".
- If there is not enough text to determine, return "unknown".
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                user_prompt,
            )

            self.log.info(
                "[curated_share] ai_language_check | ok=%s | raw=%s",
                ok_ai,
                self._shorten_for_log(raw_response, max_len=1000),
            )

            if not ok_ai or not raw_response:
                return False

            parsed = self._extract_ai_language_json(raw_response)

            if not parsed:
                self.log.info("[curated_share] IA idioma inválida. Se descarta.")
                return False

            language = str(parsed.get("language") or "").strip().lower()
            confidence = self._safe_int(parsed.get("confidence"), 0)
            reason = str(parsed.get("reason") or "").strip()

            self.log.info(
                "[curated_share] ai_language_parsed | expected=%s | detected=%s | confidence=%s | reason=%s",
                expected_language,
                language,
                confidence,
                reason,
            )

            if language != expected_language:
                return False

            if confidence < 65:
                return False

            return True

        except Exception as e:
            self.log.warning("[curated_share] error validando idioma con IA: %r", e)
            return False

    def _extract_ai_language_json(self, raw_response):
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
            self.log.warning("[curated_share] no se pudo parsear JSON IA idioma: %r", e)
            return None

    def _normalize_for_language_detection(self, text: str) -> str:
        try:
            text = str(text or "").strip().lower()

            if not text:
                return ""

            text = unicodedata.normalize("NFD", text)
            text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
            text = re.sub(r"\s+", " ", text)

            return f" {text} "

        except Exception:
            return ""

    # =========================================================
    # HELPERS
    # =========================================================
    def _clean_hashtag(self, value: str) -> str:
        value = str(value or "").strip()
        value = value.replace("#", "").strip()
        value = re.sub(r"[^A-Za-z0-9_áéíóúüñÁÉÍÓÚÜÑ]", "", value)
        return value

    def _clean_account_username(self, value: str) -> str:
        value = str(value or "").strip()
        value = value.replace("@", "").strip()

        if "instagram.com" in value:
            value = value.split("instagram.com/", 1)[-1]
            value = value.split("/", 1)[0]

        value = re.sub(r"[^A-Za-z0-9._]", "", value)
        return value

    def _safe_int(self, value, default=0) -> int:
        try:
            value = int(value)

            if value <= 0:
                return default

            return value

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