import random
import re
import unicodedata
from typing import Any, Dict, List, Optional


class InstagramCuratedSourceResolver:
    """
    Resuelve fuentes dinámicas para compartir publicaciones existentes.

    Soporta:
    - phrase
    - meme
    - local_news
    - world_news

    No quema ciudades.
    No quema cuentas locales.
    Usa:
    - custom_task.accounts / custom_task.hashtags si vienen
    - bot_personality.language
    - bot_personality.location
    """

    CONTENT_MODES = {
        "phrase",
        "meme",
        "local_news",
        "world_news",
    }

    CONTENT_MODE_ALIASES = {
        "phrase": "phrase",
        "phrases": "phrase",
        "frase": "phrase",
        "frases": "phrase",
        "quote": "phrase",
        "quotes": "phrase",
        "cita": "phrase",
        "citas": "phrase",

        "meme": "meme",
        "memes": "meme",
        "humor": "meme",

        "local_news": "local_news",
        "noticia_local": "local_news",
        "noticias_locales": "local_news",
        "local": "local_news",
        "news_local": "local_news",

        "world_news": "world_news",
        "global_news": "world_news",
        "noticia_mundial": "world_news",
        "noticias_mundiales": "world_news",
        "noticias_globales": "world_news",
        "mundial": "world_news",
        "global": "world_news",
        "world": "world_news",
    }

    AUTO_CONTENT_MODE_WEIGHTS = {
        "phrase": 30,
        "meme": 30,
        "local_news": 20,
        "world_news": 20,
    }

    DEFAULT_HASHTAGS = {
        "english": {
            "phrase": [
                "englishquotes",
                "dailyquotes",
                "quotesoftheday",
                "inspirationalquotes",
                "positivevibes",
                "mindsetquotes",
                "lifequotes",
            ],
            "meme": [
                "englishmemes",
                "relatablememes",
                "funnymemes",
                "dailymemes",
                "memeoftheday",
                "memesdaily",
                "funnyvideos",
                "englishhumor",
            ],
            "world_news": [
                "worldnews",
                "globalnews",
                "internationalnews",
                "breakingnews",
                "newsupdate",
                "currentevents",
            ],
            "local_news_fallback": [
                "localnews",
                "communitynews",
                "citynews",
                "newsupdate",
            ],
        },
        "spanish": {
            "phrase": [
                "frases",
                "frasesdeldia",
                "reflexiones",
                "motivacion",
                "pensamientos",
                "frasesmotivadoras",
            ],
            "meme": [
                "memesespanol",
                "memeslatinos",
                "humorlatino",
                "memeshispanos",
                "risas",
                "chistes",
                "memesgraciosos",
            ],
            "world_news": [
                "noticiasmundiales",
                "noticiasinternacionales",
                "ultimahora",
                "actualidad",
                "noticias",
                "noticiasglobales",
            ],
            "local_news_fallback": [
                "noticiaslocales",
                "noticiasdelacomunidad",
                "noticiasciudad",
                "actualidadlocal",
            ],
        },
    }

    LOCAL_NEWS_TEMPLATES = {
        "english": [
            "{city}news",
            "{city}localnews",
            "{city}updates",
            "{city}today",
            "{region}news",
            "localnews{city}",
        ],
        "spanish": [
            "{city}noticias",
            "noticias{city}",
            "{city}aldia",
            "actualidad{city}",
            "noticias{region}",
            "noticiaslocales{city}",
        ],
    }

    def resolve(self, data: dict, content_mode: Optional[str] = None) -> Dict[str, Any]:
        data = data or {}

        resolved_mode = self.resolve_content_mode(data, content_mode)
        language = self.get_language(data)
        location = self.get_location(data)

        custom_sources = self.resolve_custom_sources(data)
        if custom_sources:
            return {
                "content_mode": resolved_mode,
                "language": language,
                "location": location,
                "sources": custom_sources,
                "source_origin": "custom_task",
            }

        sources = self.resolve_default_sources(
            data=data,
            content_mode=resolved_mode,
            language=language,
            location=location,
        )

        return {
            "content_mode": resolved_mode,
            "language": language,
            "location": location,
            "sources": sources,
            "source_origin": "dynamic",
        }

    def resolve_content_mode(self, data: dict, content_mode: Optional[str] = None) -> str:
        custom_task = self.get_custom_task(data)

        raw_mode = (
            content_mode
            or custom_task.get("content_mode")
            or custom_task.get("mode")
            or data.get("content_mode")
            or ""
        )

        raw_mode = self.normalize_text(raw_mode)

        if raw_mode:
            resolved = self.CONTENT_MODE_ALIASES.get(raw_mode, raw_mode)

            if resolved in self.CONTENT_MODES:
                return resolved

        modes = list(self.AUTO_CONTENT_MODE_WEIGHTS.keys())
        weights = [self.AUTO_CONTENT_MODE_WEIGHTS[m] for m in modes]

        return random.choices(
            population=modes,
            weights=weights,
            k=1,
        )[0]

    def resolve_custom_sources(self, data: dict) -> List[Dict[str, str]]:
        custom_task = self.get_custom_task(data)

        accounts = (
            custom_task.get("accounts")
            or custom_task.get("source_accounts")
            or data.get("accounts")
            or []
        )

        hashtags = (
            custom_task.get("hashtags")
            or custom_task.get("source_hashtags")
            or data.get("hashtags")
            or []
        )

        accounts = self.ensure_list(accounts)
        hashtags = self.ensure_list(hashtags)

        sources = []

        for account in accounts:
            clean = self.clean_account_username(account)
            if clean:
                sources.append({"type": "account", "value": clean})

        for hashtag in hashtags:
            clean = self.clean_hashtag(hashtag)
            if clean:
                sources.append({"type": "hashtag", "value": clean})

        return self.unique_sources(sources)

    def resolve_default_sources(
        self,
        *,
        data: dict,
        content_mode: str,
        language: str,
        location: str,
    ) -> List[Dict[str, str]]:
        if content_mode in {"phrase", "meme", "world_news"}:
            tags = (
                self.DEFAULT_HASHTAGS
                .get(language, self.DEFAULT_HASHTAGS["spanish"])
                .get(content_mode, [])
            )

            return [
                {"type": "hashtag", "value": self.clean_hashtag(tag)}
                for tag in tags
                if self.clean_hashtag(tag)
            ]

        if content_mode == "local_news":
            tags = self.build_local_news_hashtags(
                location=location,
                language=language,
            )

            if not tags:
                tags = (
                    self.DEFAULT_HASHTAGS
                    .get(language, self.DEFAULT_HASHTAGS["spanish"])
                    .get("local_news_fallback", [])
                )

            return [
                {"type": "hashtag", "value": self.clean_hashtag(tag)}
                for tag in tags
                if self.clean_hashtag(tag)
            ]

        return []

    def build_local_news_hashtags(self, *, location: str, language: str) -> List[str]:
        city, region = self.parse_location(location)

        city = self.clean_hashtag_part(city)
        region = self.clean_hashtag_part(region)

        if not city:
            return []

        templates = self.LOCAL_NEWS_TEMPLATES.get(
            language,
            self.LOCAL_NEWS_TEMPLATES["spanish"],
        )

        tags = []

        for template in templates:
            if "{region}" in template and not region:
                continue

            tag = template.format(
                city=city,
                region=region,
            )

            tag = self.clean_hashtag(tag)

            if tag:
                tags.append(tag)

        return self.unique_strings(tags)

    def parse_location(self, location: str) -> tuple[str, str]:
        location = str(location or "").strip()

        if not location:
            return "", ""

        location = re.sub(r"\s+", " ", location)

        if "," in location:
            parts = [p.strip() for p in location.split(",") if p.strip()]
            city = parts[0] if parts else ""
            region = parts[1] if len(parts) > 1 else ""
            return city, region

        if "-" in location:
            parts = [p.strip() for p in location.split("-") if p.strip()]
            city = parts[0] if parts else ""
            region = parts[1] if len(parts) > 1 else ""
            return city, region

        return location, ""

    def get_language(self, data: dict) -> str:
        custom_task = self.get_custom_task(data)
        social_media_account = self.get_social_media_account(data)
        bot_personality = self.get_bot_personality(data)

        raw = (
            custom_task.get("language")
            or bot_personality.get("language")
            or social_media_account.get("language")
            or data.get("language")
            or "spanish"
        )

        value = self.normalize_text(raw)

        if value in {"en", "eng", "english", "ingles"}:
            return "english"

        if "english" in value or "ingles" in value:
            return "english"

        return "spanish"

    def get_location(self, data: dict) -> str:
        custom_task = self.get_custom_task(data)
        social_media_account = self.get_social_media_account(data)
        bot_personality = self.get_bot_personality(data)

        location = (
            custom_task.get("location")
            or bot_personality.get("location")
            or social_media_account.get("location")
            or data.get("location")
            or ""
        )

        return str(location or "").strip()

    def get_custom_task(self, data: dict) -> dict:
        value = data.get("custom_task") or {}
        return value if isinstance(value, dict) else {}

    def get_social_media_account(self, data: dict) -> dict:
        value = data.get("social_media_account") or {}
        return value if isinstance(value, dict) else {}

    def get_bot_personality(self, data: dict) -> dict:
        social_media_account = self.get_social_media_account(data)

        value = (
            social_media_account.get("bot_personality")
            or data.get("bot_personality")
            or {}
        )

        return value if isinstance(value, dict) else {}

    def ensure_list(self, value) -> list:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, tuple):
            return list(value)

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return []

            if "," in value:
                return [x.strip() for x in value.split(",") if x.strip()]

            return [value]

        return []

    def clean_account_username(self, value: str) -> str:
        value = str(value or "").strip()
        value = value.replace("@", "").strip()

        if "instagram.com" in value:
            value = value.split("instagram.com/", 1)[-1]
            value = value.split("/", 1)[0]

        value = re.sub(r"[^A-Za-z0-9._]", "", value)

        return value.strip()

    def clean_hashtag(self, value: str) -> str:
        value = str(value or "").strip()
        value = value.replace("#", "").strip()
        value = self.remove_accents(value)
        value = re.sub(r"[^A-Za-z0-9_]", "", value)
        return value.strip()

    def clean_hashtag_part(self, value: str) -> str:
        value = str(value or "").strip()
        value = self.remove_accents(value)
        value = value.lower()
        value = re.sub(r"[^a-z0-9]+", "", value)
        return value.strip()

    def normalize_text(self, text: str) -> str:
        text = str(text or "").strip().lower()

        if not text:
            return ""

        text = self.remove_accents(text)
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def remove_accents(self, text: str) -> str:
        text = str(text or "")
        text = unicodedata.normalize("NFD", text)
        return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

    def unique_strings(self, values: List[str]) -> List[str]:
        out = []
        seen = set()

        for value in values:
            value = str(value or "").strip()

            if not value:
                continue

            key = value.lower()
            if key in seen:
                continue

            seen.add(key)
            out.append(value)

        return out

    def unique_sources(self, sources: List[Dict[str, str]]) -> List[Dict[str, str]]:
        out = []
        seen = set()

        for source in sources:
            source_type = str(source.get("type") or "").strip().lower()
            source_value = str(source.get("value") or "").strip()

            if not source_type or not source_value:
                continue

            key = f"{source_type}:{source_value.lower()}"
            if key in seen:
                continue

            seen.add(key)
            out.append({
                "type": source_type,
                "value": source_value,
            })

        return out