import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.config.industry_prompt_rules import normalize_campaign_type
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService


class InstagramCampaignPolicyService:
    """
    Runtime enforcement for the migrated 03_discovery_hashtags and
    04_intro_comment_policy configuration.

    The JSON files are copied from the original campaign configuration without
    changing their contents. This service is the compatibility layer that makes
    those rules executable by the Instagram workflow.
    """

    CONFIG_DIR = (
        Path(__file__).resolve().parents[1]
        / "utils"
        / "config"
        / "instagram_policies"
    )

    @classmethod
    def _key(cls, campaign_type: Optional[str]) -> str:
        key = normalize_campaign_type(campaign_type or "")
        aliases = {
            "botanicas": "botanica",
        }
        return aliases.get(key, key)

    @classmethod
    def load_competitor_source(cls, campaign_type: Optional[str]) -> Dict[str, Any]:
        return InstagramConfigRuntimeService.load(campaign_type or "", "02_competitor_filter.json")

    @classmethod
    def competitor_prompt(cls, campaign_type: Optional[str]) -> str:
        data = cls.load_competitor_source(campaign_type)
        if not data:
            return ""
        return (
            "ORIGINAL COMPETITOR FILTER (migrated from 02_competitor_filter.json)\n"
            "Apply every source rule; the compact runtime rules are an optimization, not a replacement.\n"
            + json.dumps(data, ensure_ascii=False, indent=2)
        )

    @classmethod
    def load_discovery_policy(cls, campaign_type: Optional[str]) -> Dict[str, Any]:
        return InstagramConfigRuntimeService.load(campaign_type or "", "03_discovery_hashtags.json")

    @classmethod
    def load_comment_policy(cls, campaign_type: Optional[str]) -> Dict[str, Any]:
        return InstagramConfigRuntimeService.load(campaign_type or "", "04_intro_comment_policy.json")

    @classmethod
    def discovery_prompt(cls, campaign_type: Optional[str]) -> str:
        policy = cls.load_discovery_policy(campaign_type)
        if not policy:
            return ""
        return (
            "DISCOVERY HASHTAG POLICY (migrated from 03_discovery_hashtags.json)\n"
            + json.dumps(policy, ensure_ascii=False, indent=2)
        )

    @classmethod
    def comment_prompt(cls, campaign_type: Optional[str]) -> str:
        policy = cls.load_comment_policy(campaign_type)
        if not policy:
            return ""
        return (
            "INTRO COMMENT POLICY (migrated from 04_intro_comment_policy.json)\n"
            "The rules below are executable campaign constraints, not merely examples.\n"
            + json.dumps(policy, ensure_ascii=False, indent=2)
        )

    @classmethod
    def _normal_text(cls, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip().lower()

    @classmethod
    def _location_tokens(cls, strategy: Dict[str, Any]) -> List[str]:
        locations = strategy.get("locations") or strategy.get("target_locations") or []
        if isinstance(locations, str):
            locations = [locations]
        out = []
        for loc in locations:
            if isinstance(loc, dict):
                value = loc.get("name") or loc.get("label") or loc.get("city") or ""
            else:
                value = loc
            value = cls._normal_text(value)
            if value:
                out.append(value)
        return out

    @classmethod
    def _geo_terms(cls, policy: Dict[str, Any]) -> List[str]:
        """Return only geographic tokens declared by this industry's source policy."""
        terms: List[str] = []
        p = policy.get("policy") or {}

        if p.get("must_contain_chicago_or_suburb_or_il"):
            terms.extend(["chicago", "illinois", "il", "ill."])

        terms.extend(
            cls._normal_text(x)
            for x in (policy.get("default_service_area_tokens") or [])
            if str(x).strip()
        )

        # Some source policies express the geographic requirement inside the
        # double-validation prose rather than a dedicated token list.
        rule_text = cls._normal_text(" ".join(
            str(x) for x in (p.get("double_validation_rule") or []) if x
        ))
        if any(x in rule_text for x in ("bogota", "bogotá", "colombia")):
            terms.extend(["bogota", "bogotá", "colombia", "co"])

        # De-duplicate while preserving declaration order.
        return list(dict.fromkeys(x for x in terms if x))

    @classmethod
    def _hashtag_has_geo(cls, hashtag: str, strategy: Dict[str, Any], policy: Dict[str, Any]) -> bool:
        h = cls._normal_text(hashtag).lstrip("#")
        policy_text = json.dumps(policy, ensure_ascii=False).lower()
        locations = cls._location_tokens(strategy)
        terms = set(cls._geo_terms(policy))
        # Also derive geo tokens from configured category tags. This preserves
        # suburb/neighborhood specificity without inventing a fixed city list.
        for category in policy.get("categories") or []:
            for item in category.get("hashtags") or []:
                tag = cls._normal_text(item.get("tag") if isinstance(item, dict) else item).lstrip("#")
                if any(token and token in tag for token in terms):
                    terms.add(tag)
        # If the policy explicitly requires geo, accept a hashtag containing a
        # configured service-area/location token or a location already supplied
        # by the campaign.
        for loc in locations:
            compact = re.sub(r"[^a-z0-9áéíóúüñ]", "", loc)
            if compact and compact in re.sub(r"[^a-z0-9áéíóúüñ]", "", h):
                return True
            for word in re.findall(r"[a-záéíóúüñ]{4,}", loc):
                if word in h:
                    return True
        for token in terms:
            compact = re.sub(r"[^a-z0-9áéíóúüñ]", "", token)
            if compact and compact in re.sub(r"[^a-z0-9áéíóúüñ]", "", h):
                return True
        # For botanica, the original config is explicitly geo-preferred rather
        # than geo-only; for all other configured geo-only policies, do not
        # silently allow a global hashtag.
        return False

    @classmethod
    def _configured_removed(cls, hashtag: str, policy: Dict[str, Any]) -> bool:
        target = cls._normal_text(hashtag)
        for category in policy.get("categories") or []:
            for item in category.get("removed") or []:
                tag = item.get("tag") if isinstance(item, dict) else item
                if cls._normal_text(tag) == target:
                    return True
        return False

    @classmethod
    def _configured_allowed(cls, hashtag: str, policy: Dict[str, Any]) -> bool:
        target = cls._normal_text(hashtag)
        for category in policy.get("categories") or []:
            for item in category.get("hashtags") or []:
                tag = item.get("tag") if isinstance(item, dict) else item
                if cls._normal_text(tag) == target:
                    return True
        return False

    @classmethod
    def validate_hashtag(
        cls,
        hashtag: str,
        campaign_strategy: Optional[Dict[str, Any]] = None,
        campaign_type: Optional[str] = None,
    ) -> Tuple[bool, str]:
        strategy = campaign_strategy if isinstance(campaign_strategy, dict) else {}
        policy = cls.load_discovery_policy(campaign_type)
        if not policy:
            return True, "no_policy"

        value = str(hashtag or "").strip()
        if not value:
            return False, "empty_hashtag"

        if cls._configured_removed(value, policy):
            return False, "configured_removed"

        p = policy.get("policy") or {}
        is_geo_only = bool(p.get("geo_only"))
        requires_geo = bool(
            p.get("must_contain_chicago_or_suburb_or_il")
            or p.get("must_contain_city_or_service_area_when_possible")
        )

        if is_geo_only and requires_geo and not cls._hashtag_has_geo(value, strategy, policy):
            return False, "geo_validation_failed"

        if bool(p.get("exclude_global_hashtags")):
            # A configured hashtag is explicitly curated and is therefore not
            # considered global merely because its text lacks a city token.
            # Unlisted hashtags must pass the geo test above.
            if not cls._configured_allowed(value, policy) and not cls._hashtag_has_geo(value, strategy, policy):
                return False, "global_or_unvalidated"

        return True, "accepted"

    @classmethod
    def filter_hashtags(
        cls,
        hashtags: Iterable[str],
        campaign_strategy: Optional[Dict[str, Any]] = None,
        campaign_type: Optional[str] = None,
    ) -> Tuple[List[str], List[Tuple[str, str]]]:
        accepted, rejected = [], []
        seen = set()
        for raw in hashtags or []:
            tag = str(raw or "").strip()
            normalized = cls._normal_text(tag)
            if not tag or normalized in seen:
                continue
            seen.add(normalized)
            ok, reason = cls.validate_hashtag(tag, campaign_strategy, campaign_type)
            if ok:
                accepted.append(tag)
            else:
                rejected.append((tag, reason))
        return accepted, rejected

    @classmethod
    def _sentence_count(cls, text: str) -> int:
        parts = re.findall(r"[^.!?]+(?:[.!?]+|$)", text.strip())
        return len([p for p in parts if p.strip()])

    @classmethod
    def _emoji_count(cls, text: str) -> int:
        # Covers the emoji blocks commonly used in Instagram comments.
        return len(re.findall(
            r"[\U0001F300-\U0001FAFF\u2600-\u27BF]",
            text,
        ))

    @classmethod
    def _contains_forbidden(cls, text: str, policy: Dict[str, Any]) -> Optional[str]:
        lowered = cls._normal_text(text)
        global_rules = policy.get("global_rules") or {}
        for phrase in global_rules.get("forbidden_phrases") or []:
            p = cls._normal_text(phrase)
            if p and p in lowered:
                return str(phrase)
        for item in policy.get("banned_patterns") or []:
            bad = item.get("bad") if isinstance(item, dict) else item
            b = cls._normal_text(bad)
            if b and b in lowered:
                return str(bad)
        return None

    @classmethod
    def _accent_norm(cls, value: Any) -> str:
        import unicodedata
        text = unicodedata.normalize("NFKD", str(value or ""))
        return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()

    @classmethod
    def _context_text(cls, context: Any) -> str:
        if isinstance(context, dict):
            parts = []
            for key in ("post_caption", "caption", "text", "caption_text", "visual_description", "text_context", "post_text"):
                if context.get(key):
                    parts.append(str(context[key]))
            return cls._accent_norm(" ".join(parts))
        return cls._accent_norm(context)

    @classmethod
    def _content_tokens(cls, text: str) -> set[str]:
        stop = {"this","that","with","from","your","you","the","and","for","are","was","were","una","uno","unos","unas","que","para","con","del","las","los","por","una","un","es","de","y","en","tu","te","se","el","la","al","como","muy","más","mas","una","hoy","here","there","our","can","could","about"}
        return {w for w in re.findall(r"[a-záéíóúüñ]{5,}", cls._normal_text(text)) if w not in stop}

    @classmethod
    def _template_leak(cls, text: str, policy: Dict[str, Any], context: str) -> bool:
        """Reject copied template wording unless the same phrase is grounded in the post."""
        normalized = cls._accent_norm(text)
        ctx = cls._accent_norm(context)
        for category in policy.get("categories") or []:
            for item in category.get("templates") or []:
                template = item.get("template") if isinstance(item, dict) else ""
                if not template:
                    continue
                words = re.findall(r"[a-záéíóúüñ]{4,}", cls._accent_norm(template))
                # A 3-word sequence is enough to identify concrete copied phrasing;
                # generic 1-2 word overlap is intentionally ignored.
                for i in range(max(0, len(words)-2)):
                    phrase = " ".join(words[i:i+3])
                    if phrase in normalized and phrase not in ctx:
                        return True
        return False

    @classmethod
    def _language_ok(cls, text: str, language: str) -> bool:
        lang = cls._accent_norm(language)
        if not text or not lang:
            return True
        if lang.startswith("span") or lang in {"es","espanol"}:
            markers = {"el","la","los","las","que","para","con","una","uno","por","del","muy","puede","necesitas","gracias","estamos"}
        elif lang.startswith("port") or lang in {"pt","por"}:
            markers = {"que","para","com","uma","um","por","voce","você","estamos","pode","obrigado"}
        elif lang.startswith("eng") or lang in {"en","english"}:
            markers = {"the","and","for","with","your","you","this","that","from","can","thanks","we","are"}
        else:
            return True
        words = set(re.findall(r"[a-záéíóúüñ]{2,}", cls._accent_norm(text)))
        if len(words) < 3:
            return True
        return bool(words & {cls._accent_norm(x) for x in markers})

    @classmethod
    def validate_comment(cls, comment_text: str, campaign_type: Optional[str], used_messages: Optional[Iterable[str]] = None,
                         post_context: Any = None, account_language: Optional[str] = None) -> Tuple[bool, List[str]]:
        policy = cls.load_comment_policy(campaign_type)
        if not policy:
            return True, []

        text = str(comment_text or "").strip()
        reasons: List[str] = []
        rules = policy.get("global_rules") or {}

        if not text:
            reasons.append("empty_comment")

        max_sentences = rules.get("max_sentences")
        if isinstance(max_sentences, int) and cls._sentence_count(text) > max_sentences:
            reasons.append("max_sentences_exceeded")

        max_emoji = rules.get("emoji_max")
        if isinstance(max_emoji, int) and cls._emoji_count(text) > max_emoji:
            reasons.append("emoji_max_exceeded")

        forbidden = cls._contains_forbidden(text, policy)
        if forbidden:
            reasons.append(f"forbidden_phrase:{forbidden}")

        if not bool(rules.get("hard_cta_allowed", True)):
            hard_cta_terms = [
                "book now", "agenda ya", "agenda ahora", "reserve now",
                "reservar ahora", "schedule now", "book today",
            ]
            if any(term in cls._normal_text(text) for term in hard_cta_terms):
                reasons.append("hard_cta_not_allowed")

        used = [str(x).strip() for x in (used_messages or []) if str(x).strip()]
        lowered = cls._normal_text(text)
        if lowered in {cls._normal_text(x) for x in used}:
            reasons.append("exact_duplicate")

        if not bool(rules.get("copy_paste_mode_allowed", True)):
            for old in used:
                if SequenceMatcher(None, lowered, cls._normal_text(old)).ratio() >= 0.90:
                    reasons.append("copy_paste_similarity")
                    break

        if rules.get("allow_signature") is False:
            # Signatures are explicitly disabled by every migrated intro policy.
            # Reject conventional sign-off lines and trailing dash/name blocks
            # rather than trying to infer a person's identity from arbitrary text.
            signature_patterns = (
                r"(?im)^\s*(?:atentamente|cordialmente|saludos|sincerely|regards|best regards)[,:]?\s*$",
                r"(?im)^\s*[—–-]\s*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ .'-]{1,40}\s*$",
                r"(?im)^\s*(?:atte\.?|att\.?|firma)\s*[:\-]?\s*.+$",
            )
            if any(re.search(pattern, text) for pattern in signature_patterns):
                reasons.append("signature_not_allowed")

        if not bool(rules.get("same_template_twice_in_row_allowed", True)):
            templates = []
            for category in policy.get("categories") or []:
                for item in category.get("templates") or []:
                    value = item.get("template") if isinstance(item, dict) else ""
                    if value:
                        templates.append(cls._normal_text(value))
            if lowered in set(templates) and any(lowered == cls._normal_text(x) for x in used[-1:]):
                reasons.append("same_template_twice_in_row")

        # Deterministic enforcement of the source's semantic intro rules.
        # These checks are only applied when runtime context is available, so
        # parsers that intentionally operate without a post remain compatible.
        context = cls._context_text(post_context)
        if context:
            sentences = [x.strip() for x in re.findall(r"[^.!?]+(?:[.!?]+|$)", text) if x.strip()]
            first = sentences[0] if sentences else text
            if rules.get("first_sentence"):
                first_tokens = cls._content_tokens(first)
                context_tokens = cls._content_tokens(context)
                generic_openers = {"great post", "nice post", "love this", "love it", "awesome post", "que lindo", "muy bonito"}
                if cls._normal_text(first) in generic_openers or (first_tokens and not (first_tokens & context_tokens)):
                    reasons.append("first_sentence_not_grounded")
            if len(sentences) >= 2 and rules.get("second_sentence"):
                second = sentences[1]
                bridge_terms = {"consulta","orientacion","orientación","lectura","limpieza","ritual","servicio","assessment","consultation","audit","strategy","seo","quote","cotizacion","cotización","whatsapp","dm","privado","private","free"}
                if any(x in cls._accent_norm(second) for x in bridge_terms):
                    if not (cls._content_tokens(second) & cls._content_tokens(context)):
                        reasons.append("second_sentence_bridge_not_supported")
            if cls._template_leak(text, policy, context):
                reasons.append("template_content_not_grounded")

        if account_language and not cls._language_ok(text, account_language):
            reasons.append("language_policy_violation")

        # Config-specific declarative safety rules. These are separate from
        # industry registry safety and apply to every generated public comment.
        privacy_rule = str(rules.get("privacy_rule") or "").lower()
        if "no pedir detalles íntimos" in privacy_rule or "no pedir detalles intimos" in privacy_rule:
            if re.search(r"(?i)\b(cédula|cedula|contraseña|password|número de expediente|numero de expediente|documento|dirección exacta|direccion exacta|caso completo)\b", text):
                reasons.append("privacy_rule_violation")
        guarantee_rule = str(rules.get("no_guarantees_rule") or "").lower()
        if "no prometer resultados" in guarantee_rule or rules.get("hard_cta_allowed") is False:
            if re.search(r"(?i)\b(100%|garantiz(?:a|ado|amos)|resultado seguro|en 24 horas|vuelve en 24 horas|cura cualquier|no fallamos)\b", text):
                reasons.append("no_guarantees_rule_violation")

        return not reasons, reasons
