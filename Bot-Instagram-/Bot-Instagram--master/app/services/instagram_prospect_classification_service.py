import json
from pathlib import Path
import re
from typing import Any, Optional

from app.config.industry_prompt_rules import normalize_campaign_type
from app.services.instagram_campaign_policy_service import InstagramCampaignPolicyService
from app.services.instagram_config_policy_engine import InstagramConfigPolicyEngine
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService


class InstagramProspectClassificationService:
    """
    Clasificador de prospectos para Instagram.

    Responsabilidades:
    - detectar industria
    - detectar competencia
    - clasificar tipo de perfil
    - clasificar rol comercial
    - detectar vertical
    - medir intención comercial
    - cargar reglas específicas por industria

    NO:
    - abre Instagram
    - hace Selenium
    - sigue perfiles
    - comenta
    - guarda prospectos
    """

    DEFAULT_INDUSTRY = "cleaning"

    INDUSTRY_ALIASES = {
        "botanica espiritual": "botanica",
        "botánica espiritual": "botanica",
        "botanica": "botanica",
        "spiritual products": "botanica",
        "spiritual supplies": "botanica",
        "ritual products": "botanica",
        "religious supplies": "botanica",

        "attorney": "abogados",
        "attorneys": "abogados",
        "law firm": "abogados",
        "legal services": "abogados",
        "legal service": "abogados",

        "fences": "fences",
        "fence": "fences",
        "fence installation": "fences",
        "cercas": "fences",

        "spa": "spa",
        "spa colombia": "spa colombia",

        "abogados": "abogados",
        "abogado": "abogados",
        "legal": "abogados",
        "law": "abogados",

        "marketing": "marketing",
        "digital marketing": "marketing",

        "cleaning": "cleaning",
        "commercial cleaning": "cleaning",
        "limpieza": "cleaning",

        "real estate": "real_estate",
        "realestate": "real_estate",
        "real estate agent": "real_estate",
        "realtor": "real_estate",
        "realtors": "real_estate",
        "property management": "real_estate",
        "property manager": "real_estate",

        "construction": "construction",
        "contractor": "construction",
        "general contractor": "construction",
        "remodeling": "construction",
        "renovation": "construction",

        "landscaping": "landscaping",
        "landscape": "landscaping",
        "lawn care": "landscaping",

        "plumbing": "plumbing",
        "plumber": "plumbing",
        "hvac": "hvac",
        "heating and cooling": "hvac",
        "roofing": "roofing",
        "roofer": "roofing",
        "insurance": "insurance",
        "finance": "finance",
        "accounting": "accounting",
        "accountant": "accounting",
        "marketing": "marketing",
        "digital marketing": "marketing",
    }

    PROFILE_CLASSIFICATIONS = {
        "BUSINESS",
        "PROFESSIONAL",
        "EMPLOYEE",
        "PERSONAL",
        "CREATOR",
        "ORGANIZATION",
        "COMMON_PERSON",
        "SPIRITUAL_CONTENT_PAGE",
        "INDEPENDENT_SPIRITUAL_SPECIALIST",
        "INDEPENDENT_NICHE_SPECIALIST",
        "COMPANY_AFFILIATED_PROFESSIONAL",
        "LOCAL_BUSINESS_OWNER",
        "LOCAL_BUSINESS_PAGE",
        "NON_LOCAL_OR_UNRELATED_BUSINESS",
        "UNKNOWN",
    }

    PROFILE_CLASSIFICATION_ALIASES = {
        "SPIRITUAL_CONTENT_PAGE": "SPIRITUAL_CONTENT_PAGE",
        "INDEPENDENT_SPIRITUAL_SPECIALIST": "INDEPENDENT_SPIRITUAL_SPECIALIST",
    }

    BUSINESS_ROLES = {
        "NONE",
        "INDEPENDENT_WORKER",
        "AGENT_OR_REPRESENTATIVE",
        "BROKER",
        "SPECIALIST",
        "DOCTOR_OR_HEALTH_PROFESSIONAL",
        "BUSINESS_OWNER",
        "COMPANY_PAGE",
        "EMPLOYEE",
        "CONTRACTOR",
        "REALTOR",
        "PROPERTY_MANAGER",
        "SERVICE_PROVIDER",
        "CREATOR",
        "SPIRITUAL_CONTENT_CREATOR",
        "UNKNOWN",
    }

    BUSINESS_VERTICALS = {
        "CLEANING",
        "FENCING",
        "GATES_ACCESS_CONTROL",
        "IRON_RAILINGS_BOLLARDS",
        "BOTANICA_SPIRITUAL",
        "ESOTERIC_STORE",
        "TAROT_READING",
        "ASTROLOGY_HOROSCOPE",
        "PSYCHIC_VIDENTE",
        "WITCHCRAFT_BRUJERIA",
        "SANTERIA",
        "SPIRITUAL_CLEANSING",
        "LOVE_SPELLS_AMARRES",
        "SPIRITUAL_CONTENT",
        "RELIGIOUS_OR_SPIRITUAL_COMMUNITY",
        "OTHER_SPIRITUAL_SERVICE",
        "REAL_ESTATE",
        "CONSTRUCTION",
        "HANDYMAN",
        "MOVING",
        "LANDSCAPING",
        "INSURANCE",
        "FINANCE",
        "RETAIL",
        "FOOD",
        "BEAUTY",
        "HEALTH",
        "AUTOMOTIVE",
        "OTHER_SERVICE",
        "UNRELATED_BUSINESS",
        "PERSONAL",
        "UNKNOWN",
    }

    COMPETITOR_RELATIONS = {
        "DIRECT_COMPETITOR",
        "POSSIBLE_COMPETITOR",
        "DIRECT_FENCE_COMPETITOR",
        "POSSIBLE_FENCE_COMPETITOR",
        "DIRECT_BOTANICA_COMPETITOR",
        "SPIRITUAL_CONTENT_COMPETITOR",
        "POSSIBLE_SPIRITUAL_COMPETITOR",
        "ADJACENT_SPIRITUAL_OR_RELIGIOUS",
        "DIRECT_LEGAL_COMPETITOR",
        "POSSIBLE_LEGAL_COMPETITOR",
        "ADJACENT_LOCAL_SERVICE",
        "UNRELATED_BUSINESS",
        "PERSONAL_PROFILE",
        "UNKNOWN",
    }

    COMPETITOR_RELATION_ALIASES = {
        "DIRECT_FENCE_COMPETITOR": "DIRECT_COMPETITOR",
        "POSSIBLE_FENCE_COMPETITOR": "POSSIBLE_COMPETITOR",
        "DIRECT_BOTANICA_COMPETITOR": "DIRECT_COMPETITOR",
        "SPIRITUAL_CONTENT_COMPETITOR": "DIRECT_COMPETITOR",
        "POSSIBLE_SPIRITUAL_COMPETITOR": "POSSIBLE_COMPETITOR",
        "ADJACENT_SPIRITUAL_OR_RELIGIOUS": "ADJACENT_LOCAL_SERVICE",
        "DIRECT_LEGAL_COMPETITOR": "DIRECT_COMPETITOR",
        "POSSIBLE_LEGAL_COMPETITOR": "POSSIBLE_COMPETITOR",
    }

    # Generic signals used only to infer a missing campaign target from its
    # configuration. They never replace the AI-detected industry of a profile.
    INDUSTRY_SERVICE_SIGNALS = {
        "botanica": ("botanica", "spiritual products", "spiritual supplies", "herbal products", "ritual products", "religious supplies", "spiritual consultations"),
        "real_estate": ("real estate", "realtor", "property", "home buying", "home selling", "leasing", "real estate investment", "property management"),
        "construction": ("construction", "contractor", "remodel", "renovation", "builder"),
        "cleaning": ("cleaning", "janitorial", "maid", "deep cleaning", "move in cleaning", "post construction cleaning"),
        "landscaping": ("landscaping", "landscape", "lawn care", "yard care"),
        "plumbing": ("plumbing", "plumber"),
        "hvac": ("hvac", "heating", "air conditioning", "cooling"),
        "roofing": ("roofing", "roofer", "roof replacement"),
        "insurance": ("insurance", "insurance agent", "insurance services"),
        "finance": ("finance", "financial", "loans", "lending", "mortgage"),
        "accounting": ("accounting", "accountant", "tax preparation", "bookkeeping"),
        "marketing": ("marketing", "digital marketing", "social media management", "lead generation", "advertising"),
        "fences": ("fence installation", "fencing", "fences", "gates"),
    }

    PROFILE_STRONG_PERSONAL_SIGNALS = (
        "just sharing moments", "friends and family", "personal account",
        "my personal life", "mom life", "dad life", "husband", "wife",
    )
    PROFILE_STRONG_BUSINESS_SIGNALS = (
        "contact", "book", "booking", "quote", "estimate", "services",
        "serving", "company", "business", "llc", "inc", "agency",
        "shop", "studio", "office", "contractor", "realtor", "broker",
        "property management", "call us", "email us", "get a quote",
    )

    def __init__(self, ai_api, logger=None):
        self.ai_api = ai_api
        self.log = logger

    # =========================================================
    # PUBLIC
    # =========================================================

    def classify(
        self,
        bot_personality_id: int,
        campaign: dict,
        profile_context: dict,
        post_context: dict,
        recent_posts: Optional[list[dict]] = None,
    ) -> tuple[bool, dict]:

        campaign = campaign or {}
        profile_context = profile_context or {}
        post_context = post_context or {}
        recent_posts = recent_posts or []

        try:
            # -------------------------------------------------
            # 1. Detectar industria
            # -------------------------------------------------

            industry = self.detect_campaign_industry(campaign)

            # -------------------------------------------------
            # 2. Revisar competidor obvio
            #
            # Esto ocurre ANTES de llamar a la IA.
            # -------------------------------------------------

            obvious_competitor = self.detect_obvious_competitor(
                campaign=campaign,
                profile_context=profile_context,
                post_context=post_context,
                recent_posts=recent_posts,
            )

            if obvious_competitor:

                if self.log:
                    self.log.info(
                        "[instagram-classifier] "
                        "obvious competitor detected: %s",
                        profile_context.get("username"),
                    )

                return True, obvious_competitor

            # -------------------------------------------------
            # 3. Cargar y ejecutar reglas deterministas del config
            # -------------------------------------------------

            rules = self.load_competitor_rules(industry)
            policy = InstagramConfigPolicyEngine.evaluate_competitor(
                campaign_type=industry,
                profile=profile_context,
                post=post_context,
                recent=recent_posts,
            )
            source_text = " ".join([
                str(profile_context.get("bio") or ""),
                str(profile_context.get("profile_description") or ""),
                str(post_context.get("caption_text") or ""),
                str(post_context.get("text_context") or ""),
            ])
            registry_policy = InstagramConfigPolicyEngine.enforce_registry_rules(
                campaign_type=industry,
                text=source_text,
                profile=profile_context,
                post=post_context,
            )
            if registry_policy["blocked"] and (registry_policy["skip_post"] or registry_policy["human_escalation"]):
                return True, {
                    "competitor_score": policy.get("competitor_score", 0),
                    "is_competitor": False,
                    "is_blacklisted": False,
                    "blacklist_reason": "",
                    "profile_classification": "UNKNOWN",
                    "business_role": "UNKNOWN",
                    "business_vertical": "UNKNOWN",
                    "competitor_relation": "UNKNOWN",
                    "commercial_intent_score": 0,
                    "qualification_score": 0,
                    "qualification_decision": "DISCARDED",
                    "engageable": False,
                    "classification_confidence": 100,
                    "classification_evidence": registry_policy["reasons"],
                    "industry_detected": industry,
                    "location_match": None,
                    "location_confidence": "low",
                    "location_evidence": [],
                    "skip_post": True,
                    "mode": "skip",
                    "selected_service": "",
                    "request_directness": "none",
                    "b2b_target_type": "",
                    "b2b_angle": "",
                    "b2b_confidence": "low",
                    "comment": "",
                    "notes": "Regla determinista del registry activada: " + ", ".join(registry_policy["reasons"]),
                    "human_escalation_required": bool(registry_policy["human_escalation"]),
                    "urgency_detected": bool(registry_policy["urgent"]),
                }

            if policy.get("decision") == "BLOCK":
                return True, {
                    "competitor_score": policy["competitor_score"],
                    "is_competitor": True,
                    "is_blacklisted": True,
                    "blacklist_reason": policy.get("blacklist_reason") or "Competitor rule matched.",
                    "profile_classification": "BUSINESS",
                    "business_role": "UNKNOWN",
                    "business_vertical": "UNKNOWN",
                    "competitor_relation": "DIRECT_COMPETITOR",
                    "commercial_intent_score": 0,
                    "qualification_score": 0,
                    "qualification_decision": "DISCARDED",
                    "engageable": False,
                    "classification_confidence": 100,
                    "classification_evidence": policy.get("layers") or [],
                    "industry_detected": industry,
                    "location_match": None,
                    "location_confidence": "low",
                    "location_evidence": [],
                    "skip_post": True,
                    "mode": "skip",
                    "selected_service": "",
                    "request_directness": "none",
                    "b2b_target_type": "",
                    "b2b_angle": "",
                    "b2b_confidence": "low",
                    "comment": "",
                    "notes": "Deterministic competitor filter: " + str(policy.get("blacklist_reason") or "block"),
                }

            # Conservative early screen: only reject an account before the
            # expensive post/recent-post analysis when the profile itself is
            # strongly personal and explicitly tied to an employer.
            if self._looks_like_personal_employee(profile_context, post_context, recent_posts):
                return True, self._build_personal_skip_result(industry, campaign)

            # -------------------------------------------------
            # 4. Construir prompt
            # -------------------------------------------------

            rules_for_prompt = dict(rules)
            rules_for_prompt["deterministic_runtime_evaluation"] = {
                "decision": policy.get("decision"),
                "competitor_score": policy.get("competitor_score"),
                "review_required": policy.get("review_required"),
                "layers": policy.get("layers"),
            }
            prompt = self.build_prompt(
                campaign=campaign,
                industry=industry,
                rules=rules_for_prompt,
                profile_context=profile_context,
                post_context=post_context,
                recent_posts=recent_posts,
            )

            if self.log:
                self.log.info(
                    "[instagram-classifier] industry=%s",
                    industry,
                )

                self.log.info(
                    "[instagram-classifier] profile=%s",
                    profile_context.get("username"),
                )

            # -------------------------------------------------
            # 5. IA
            # -------------------------------------------------

            ok_ai, raw_response = (
                self.ai_api.get_bot_ia_long_prompt(
                    bot_personality_id,
                    prompt,
                )
            )

            if not ok_ai or not raw_response:

                if self.log:
                    self.log.warning(
                        "[instagram-classifier] "
                        "AI did not return classification"
                    )

                return False, {
                    "error": "AI did not return classification"
                }

            # -------------------------------------------------
            # 6. Parsear JSON
            # -------------------------------------------------

            parsed = self.parse_response(raw_response)

            if not parsed:

                if self.log:
                    self.log.warning(
                        "[instagram-classifier] invalid AI JSON"
                    )

                return False, {
                    "error": "Invalid classification JSON"
                }

            # -------------------------------------------------
            # 7. Normalizar resultado
            # -------------------------------------------------

            normalized = self.normalize_result(
                parsed=parsed,
                industry=industry,
            )

            normalized["profile_classification"] = self._infer_profile_classification(
                profile_context, post_context, recent_posts, normalized.get("profile_classification", "UNKNOWN")
            )
            normalized["business_role"] = self._infer_business_role(
                profile_context, post_context, normalized.get("business_role", "UNKNOWN")
            )
            normalized["business_vertical"] = self._infer_business_vertical(
                profile_context,
                post_context,
                recent_posts,
                normalized.get("business_vertical", "UNKNOWN"),
                normalized.get("industry_detected", "unknown"),
            )
            if normalized.get("industry_detected") in {"unknown", "", None}:
                vertical_to_industry = {
                    "FOOD": "food",
                    "BEAUTY": "beauty",
                    "AUTOMOTIVE": "automotive",
                    "RETAIL": "retail",
                    "CLEANING": "cleaning",
                    "LANDSCAPING": "landscaping",
                    "REAL_ESTATE": "real_estate",
                    "CONSTRUCTION": "construction",
                }
                normalized["industry_detected"] = vertical_to_industry.get(
                    normalized.get("business_vertical"),
                    "unknown",
                )

            # Deterministic REVIEW means the candidate cannot be engaged unless
            # the second-stage AI review is sufficiently confident and non-competitive.
            if policy.get("decision") == "REVIEW":
                ai_conf = int(normalized.get("classification_confidence") or 0)
                ai_comp = bool(normalized.get("is_competitor") or normalized.get("is_blacklisted"))
                if ai_comp or ai_conf < 70:
                    normalized["skip_post"] = True
                    normalized["mode"] = "skip"
                    normalized["request_directness"] = "none"
                    normalized["selected_service"] = ""
                    normalized["comment"] = ""
                    normalized["qualification_decision"] = "DISCARDED"
                    normalized["engageable"] = False
                    normalized["notes"] = "REVIEW 30-59: segunda revisión IA no alcanzó el umbral de seguridad."
                else:
                    normalized["notes"] = "REVIEW 30-59: segunda revisión IA superada."

            normalized["human_escalation_required"] = bool(registry_policy.get("human_escalation"))
            normalized["urgency_detected"] = bool(registry_policy.get("urgent"))
            normalized["registry_rule_reasons"] = registry_policy.get("reasons") or []

            # -------------------------------------------------
            # 8. Validar coherencia
            # -------------------------------------------------

            normalized = self._enforce_location_evidence(
                result=normalized,
                campaign=campaign,
                profile_context=profile_context,
                post_context=post_context,
                recent_posts=recent_posts,
            )

            normalized = self._recover_service_prospecting_candidate(
                result=normalized,
                campaign=campaign,
                profile_context=profile_context,
                post_context=post_context,
                recent_posts=recent_posts,
            )

            normalized = self.validate_result(
                result=normalized,
                industry=industry,
                campaign=campaign,
            )

            # Validate the selected offer against the campaign snapshot.
            # Never let the model invent a service that is not actually sold.
            services = campaign.get("services_snapshot") or []
            if not isinstance(services, list):
                services = [services]
            normalized_services = {
                self.normalize_text(item): str(item).strip()
                for item in services
                if str(item or "").strip()
            }

            if not normalized.get("skip_post") and normalized_services:
                selected = self.normalize_text(
                    normalized.get("selected_service")
                )
                if selected not in normalized_services:
                    normalized["selected_service"] = ""
                    normalized["skip_post"] = True
                    normalized["mode"] = "skip"
                    normalized["request_directness"] = "none"
                    normalized["b2b_confidence"] = "low"
                    normalized["comment"] = ""
                    normalized["notes"] = (
                        "La IA no seleccionó un servicio válido de la campaña; "
                        "se evita inventar una oferta."
                    )
                else:
                    normalized["selected_service"] = normalized_services[selected]

            return True, normalized

        except Exception as exc:

            if self.log:
                self.log.exception(
                    "[instagram-classifier] classification error"
                )

            return False, {
                "error": str(exc)
            }

    def _build_personal_skip_result(self, industry: str, campaign: dict) -> dict:
        locations = self.extract_campaign_locations(campaign)
        return {
            "competitor_score": 0,
            "is_competitor": False,
            "is_blacklisted": False,
            "blacklist_reason": "",
            "profile_classification": "EMPLOYEE",
            "business_role": "EMPLOYEE",
            "business_vertical": "PERSONAL",
            "competitor_relation": "PERSONAL_PROFILE",
            "commercial_intent_score": 0,
            "classification_confidence": 95,
            "classification_evidence": ["La cuenta parece personal y la evidencia la vincula con un empleador, no con un negocio propio."],
            "industry_detected": "unknown",
            "location_match": True if not locations else None,
            "location_confidence": "low" if locations else "high",
            "location_evidence": [] if locations else ["La campaña no define restricciones geográficas."],
            "skip_post": True,
            "mode": "skip",
            "selected_service": "",
            "b2b_target_type": "",
            "b2b_angle": "",
            "b2b_confidence": "low",
            "request_directness": "none",
            "service_match_reason": "",
            "comment": "",
            "notes": "Early profile screen: personal employee account.",
        }

    # =========================================================
    # DETERMINISTIC COMPETITOR CHECK
    # =========================================================

    def detect_obvious_competitor(
        self, campaign: dict, profile_context: dict, post_context: Optional[dict] = None, recent_posts: Optional[list[dict]] = None
    ) -> Optional[dict]:
        """Compatibility entry point backed exclusively by 02_competitor_filter.json.

        It never reads the legacy utils/config competitor lists, preventing two
        competing sources of truth. REVIEW is deliberately left for the full
        classifier/AI path; only source-config BLOCK is an early hard stop.
        """
        industry = self.detect_campaign_industry(campaign or {})
        policy = InstagramConfigPolicyEngine.evaluate_competitor(industry, profile_context or {}, post_context or {}, recent_posts or [])
        if policy.get("decision") != "BLOCK":
            return None
        return {
            "competitor_score": policy.get("competitor_score", 0),
            "is_competitor": True, "is_blacklisted": True,
            "blacklist_reason": policy.get("blacklist_reason") or "Competitor rule matched.",
            "profile_classification": "BUSINESS", "business_role": "UNKNOWN", "business_vertical": "UNKNOWN",
            "competitor_relation": "DIRECT_COMPETITOR", "commercial_intent_score": 0,
            "qualification_score": 0, "qualification_decision": "DISCARDED", "engageable": False,
            "classification_confidence": 100, "classification_evidence": policy.get("layers") or [],
            "industry_detected": industry, "location_match": None, "location_confidence": "low",
            "location_evidence": [], "skip_post": True, "mode": "skip", "selected_service": "",
            "request_directness": "none", "b2b_target_type": "", "b2b_angle": "", "b2b_confidence": "low",
            "comment": "", "notes": "Deterministic competitor filter from 02_competitor_filter.json.",
        }

    def is_service_prospecting_campaign(
        self,
        campaign: dict,
        industry: Optional[str] = None,
    ) -> bool:
        """Whether the campaign sells a service to businesses in other industries.

        Marketing campaigns are a special case: their services are the offer, not
        the industry of the prospect. This prevents a campaign such as
        "Chicago Marketing" from treating every non-marketing business as invalid.
        An explicit prospect industry can still override this behaviour when the
        backend supplies ``industry_target``/``industry``.
        """
        campaign = campaign or {}
        explicit_target = campaign.get("industry_target") or campaign.get("industry")
        if explicit_target:
            return False
        strategy = campaign.get("strategy_snapshot") or {}
        if not isinstance(strategy, dict):
            strategy = {}
        if strategy.get("industry_target") or strategy.get("industry"):
            return False
        return (industry or self.detect_campaign_industry(campaign)) == "marketing"

    def detect_campaign_industry(
        self,
        campaign: dict,
    ) -> str:
        """Return the campaign *target* industry, never a prospect industry.

        Priority is explicit configuration first. If the backend omitted the
        field, infer conservatively from campaign services/name/strategy so a
        campaign such as "Chicago Real Estate" with real-estate services does
        not silently fall back to the historical default (cleaning).
        """
        campaign = campaign or {}
        strategy = campaign.get("strategy_snapshot") or {}
        if not isinstance(strategy, dict):
            strategy = {}

        explicit = [
            campaign.get("industry_target"),
            campaign.get("industry"),
            campaign.get("campaign_type"),
            campaign.get("category"),
            strategy.get("industry_target"),
            strategy.get("industry"),
            strategy.get("vertical"),
            strategy.get("campaign_type"),
            strategy.get("category"),
        ]
        for value in explicit:
            normalized = self.normalize_text(value)
            if not normalized:
                continue
            if normalized in self.INDUSTRY_ALIASES:
                return self.INDUSTRY_ALIASES[normalized]
            for alias, directory in self.INDUSTRY_ALIASES.items():
                alias_normalized = self.normalize_text(alias)
                if alias_normalized and re.search(
                    rf"(?<!\w){re.escape(alias_normalized)}(?!\w)",
                    normalized,
                ):
                    return directory

        services = campaign.get("services_snapshot") or strategy.get("services") or []
        if not isinstance(services, list):
            services = [services]
        haystack = self.normalize_text(" ".join(str(x) for x in services if x))
        haystack += " " + self.normalize_text(campaign.get("name"))
        haystack += " " + self.normalize_text(campaign.get("handle"))

        best = None
        best_score = 0
        for industry_name, signals in self.INDUSTRY_SERVICE_SIGNALS.items():
            score = sum(1 for signal in signals if self.normalize_text(signal) in haystack)
            if score > best_score:
                best = industry_name
                best_score = score
        return best or self.DEFAULT_INDUSTRY

    def extract_campaign_locations(self, campaign: dict) -> list[str]:
        campaign = campaign or {}
        strategy = campaign.get("strategy_snapshot") or {}
        if not isinstance(strategy, dict):
            strategy = {}
        raw = campaign.get("locations")
        if raw is None:
            raw = strategy.get("locations")
        if not isinstance(raw, list):
            raw = [raw] if raw else []
        result, seen = [], set()
        for item in raw:
            value = str(item or "").strip()
            key = self.normalize_location_text(value)
            if value and key and key not in seen:
                seen.add(key)
                result.append(value)
        return result

    @staticmethod
    def normalize_location_text(value: Any) -> str:
        import re
        import unicodedata
        text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
        text = text.lower().replace("&", " and ")
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _location_evidence_quality(cls, evidence: list[str]) -> str:
        text = cls.normalize_location_text(" ".join(evidence))
        if not text:
            return "low"
        strong = ("serving", "based in", "located in", "office in", "headquartered",
                  "our location", "address", "contact us", "service area", "areas we serve")
        medium = ("project in", "client in", "clients in", "works in", "working in",
                  "commercial property in", "listing in", "job in")
        if any(x in text for x in strong):
            return "high"
        if any(x in text for x in medium):
            return "medium"
        return "low"

    @classmethod
    def _looks_like_personal_employee(cls, profile_context: dict, post_context: dict, recent_posts: list[dict]) -> bool:
        values = [profile_context.get("bio"), profile_context.get("display_name"), profile_context.get("username")]
        text = cls.normalize_text(" ".join(str(v or "") for v in values))
        evidence = cls.normalize_text(" ".join(str(v or "") for v in [post_context.get("caption_text"), post_context.get("text_context")]))
        evidence += " " + cls.normalize_text(" ".join(str(p.get("caption_text") or p.get("text_context") or "") for p in recent_posts if isinstance(p, dict)))
        personal = sum(1 for s in cls.PROFILE_STRONG_PERSONAL_SIGNALS if cls.normalize_text(s) in text)
        business = sum(1 for s in cls.PROFILE_STRONG_BUSINESS_SIGNALS if cls.normalize_text(s) in text)
        employee_terms = ("works at", "employee", "team member", "associate at", "staff at", "works for")
        employee = any(s in text + " " + evidence for s in employee_terms)
        return employee and business == 0 and (personal > 0 or not any(cls.normalize_text(s) in text for s in cls.PROFILE_STRONG_BUSINESS_SIGNALS))

    @classmethod
    def _infer_profile_classification(cls, profile_context: dict, post_context: dict, recent_posts: list[dict], current: str) -> str:
        """Conservative deterministic fallback when AI returns UNKNOWN."""
        if current != "UNKNOWN":
            return current
        values = [
            profile_context.get("username"),
            profile_context.get("display_name"),
            profile_context.get("bio"),
            post_context.get("caption_text"),
            post_context.get("text_context"),
        ]
        for post in recent_posts or []:
            if isinstance(post, dict):
                values.extend([post.get("caption_text"), post.get("text_context")])
        text = cls.normalize_text(" ".join(str(v or "") for v in values))
        if not text:
            return current

        employee_terms = ("works at", "works for", "employee", "team member", "staff at", "associate at")
        personal_terms = ("personal account", "my personal life", "friends and family", "mom life", "dad life")
        business_terms = (
            "llc", "inc", "company", "agency", "services", "serving", "contact", "book", "booking",
            "quote", "estimate", "realtor", "real estate", "broker", "contractor", "property management",
            "office", "studio", "shop", "business", "get a quote", "call us", "email us"
        )
        has_employee = any(cls.normalize_text(x) in text for x in employee_terms)
        self_business_terms = ("my company", "my business", "owner", "founder", "co-owner", "our company", "i own", "we offer", "i offer")
        has_self_business = any(cls.normalize_text(x) in text for x in self_business_terms)
        if has_employee and not has_self_business:
            return "EMPLOYEE"
        if any(cls.normalize_text(x) in text for x in personal_terms):
            return "PERSONAL"
        if any(cls.normalize_text(x) in text for x in business_terms):
            return "BUSINESS"
        return current

    @classmethod
    def _infer_business_vertical(
        cls,
        profile_context: dict,
        post_context: dict,
        recent_posts: list[dict],
        current: str,
        industry_detected: str,
    ) -> str:
        """Infer a missing business vertical from concrete profile/post evidence."""
        if current != "UNKNOWN":
            return current

        detected = cls.normalize_text(industry_detected)
        industry_to_vertical = {
            "cleaning": "CLEANING",
            "fences": "CONSTRUCTION",
            "botanica": "BOTANICA_SPIRITUAL",
            "spa": "BEAUTY",
            "spa colombia": "BEAUTY",
            "abogados": "OTHER_SERVICE",
            "real estate": "REAL_ESTATE",
            "realestate": "REAL_ESTATE",
            "construction": "CONSTRUCTION",
            "landscaping": "LANDSCAPING",
            "food": "FOOD",
            "food beverage": "FOOD",
            "food & beverage": "FOOD",
            "catering": "FOOD",
            "baking": "FOOD",
            "restaurant": "FOOD",
            "restaurants": "FOOD",
            "beauty": "BEAUTY",
            "automotive": "AUTOMOTIVE",
            "retail": "RETAIL",
        }
        if detected in industry_to_vertical:
            return industry_to_vertical[detected]

        values = [
            profile_context.get("username"),
            profile_context.get("display_name"),
            profile_context.get("bio"),
            post_context.get("caption_text"),
            post_context.get("text_context"),
        ]
        values.extend(
            p.get("caption_text") or p.get("text_context") or ""
            for p in recent_posts or []
            if isinstance(p, dict)
        )
        text = cls.normalize_text(" ".join(str(v or "") for v in values))
        vertical_signals = (
            (("restaurant", "restaurant business", "caterer", "catering", "baker", "bakery", "food business", "food and beverage", "food & beverage"), "FOOD"),
            (("salon", "hair salon", "beauty", "esthetician", "nail", "barber"), "BEAUTY"),
            (("car dealer", "auto repair", "automotive", "mechanic", "car wash"), "AUTOMOTIVE"),
            (("retail", "boutique", "store", "shop", "ecommerce", "e-commerce"), "RETAIL"),
            (("cleaning", "janitorial", "maid service"), "CLEANING"),
            (("landscaping", "lawn care", "landscape"), "LANDSCAPING"),
            (("realtor", "real estate", "property management", "property manager"), "REAL_ESTATE"),
            (("contractor", "construction", "remodel", "renovation"), "CONSTRUCTION"),
        )
        for terms, vertical in vertical_signals:
            if any(cls.normalize_text(term) in text for term in terms):
                return vertical
        return current

    @classmethod
    def _infer_business_role(cls, profile_context: dict, post_context: dict, current: str) -> str:
        if current != "UNKNOWN":
            return current
        text = cls.normalize_text(" ".join(str(profile_context.get(k) or "") for k in ("username", "display_name", "bio")) + " " + str(post_context.get("caption_text") or ""))
        patterns = [
            (("property manager", "property management"), "PROPERTY_MANAGER"),
            (("realtor", "real estate agent", "real estate"), "REALTOR"),
            (("broker",), "BROKER"),
            (("contractor", "general contractor"), "CONTRACTOR"),
            (("owner", "founder", "business owner"), "BUSINESS_OWNER"),
            (("company", "llc", "inc", "agency"), "COMPANY_PAGE"),
        ]
        for terms, role in patterns:
            if any(cls.normalize_text(term) in text for term in terms):
                return role
        return current

    # =========================================================
    # CONFIG
    # =========================================================

    def load_competitor_rules(
        self,
        industry: str,
    ) -> dict:
        # Canonical source: app/config/business_config/<industry>/02_competitor_filter.json.
        # Do not fall back to legacy compact copies under utils/config: those
        # documents have a different schema and can drift from the migrated
        # source used by the deterministic policy engine.
        key = normalize_campaign_type(industry) or self.DEFAULT_INDUSTRY
        rules = InstagramConfigRuntimeService.load(key, "02_competitor_filter.json")
        if not rules and self.log:
            self.log.warning(
                "[instagram-classifier] competitor rules not found for industry=%s",
                key,
            )
        return rules

    # =========================================================
    # PROMPT
    # =========================================================

    def _load_long_form_classification_rules(self, industry: str) -> str:
        key = normalize_campaign_type(industry)
        # Do not inject legacy Facebook classifier prompts when their content
        # is not a trustworthy source for the Instagram classifier.
        #
        # In particular, spa_classification_prompt.txt is contaminated with
        # the fence classifier (the file starts with fence/fence-installation
        # rules). Injecting it into a spa campaign would apply the wrong
        # competitor rubric. Spa classification must therefore rely on the
        # campaign's structured competitor_filter JSON instead.
        #
        # Marketing has the separate service-prospecting contract and its
        # legacy Facebook classifier is also intentionally excluded.
        if key in {"marketing", "spa"}:
            return ""

        path = Path(__file__).resolve().parents[1] / "config" / "prompts" / "facebook_compatible" / f"{key}_classification_prompt.txt"
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except OSError:
            pass
        return ""

    def build_prompt(
        self,
        campaign: dict,
        industry: str,
        rules: dict,
        profile_context: dict,
        post_context: dict,
        recent_posts: list[dict],
    ) -> str:

        campaign = campaign or {}
        strategy = campaign.get(
            "strategy_snapshot"
        ) or {}

        if not isinstance(strategy, dict):
            strategy = {}

        services = campaign.get(
            "services_snapshot"
        ) or []

        if not isinstance(services, list):
            services = [services]

        campaign_type = (
            campaign.get("campaign_type")
            or campaign.get("category")
            or campaign.get("industry")
            or strategy.get("campaign_type")
            or strategy.get("category")
            or strategy.get("industry")
            or industry
        )

        service_prospecting = self.is_service_prospecting_campaign(campaign, industry)

        campaign_info = {
            "id": campaign.get("id"),
            "name": campaign.get("name"),
            "campaign_type": campaign_type,
            "industry_target": industry,
            "service_prospecting_campaign": service_prospecting,
            "services_snapshot": services,
            "strategy_snapshot": strategy,
        }

        # Marketing is a SERVICE-PROSPECTING campaign in this bot.  The old
        # Facebook-compatible marketing prompt is a legacy spa/aesthetics
        # competitor prompt and is not applicable here. Including it makes the
        # model classify ordinary local businesses with the wrong rubric.
        long_form_rules = self._load_long_form_classification_rules(industry)
        original_competitor_rules = InstagramCampaignPolicyService.competitor_prompt(campaign_type)
        discovery_policy = InstagramCampaignPolicyService.discovery_prompt(campaign_type)
        prospecting_instruction = (
            "This is a SERVICE-PROSPECTING campaign. The campaign sells digital marketing services to local businesses. "
            "Do NOT require industry_detected to equal marketing. Restaurants, contractors, salons, real estate businesses, "
            "cleaning companies, retailers, professionals and other local businesses can be valid prospects. "
            "Only marketing/advertising/SEO/social-media agencies and providers offering the same core services are competitors. "
            "For a non-competitor local business, evaluate whether the supplied evidence supports a plausible marketing opportunity. "
            "Do not require the post to explicitly ask for marketing help; a business with a clear commercial presence can qualify "
            "when the evidence supports a reasonable service fit. "
            if service_prospecting else ""
        )

        return f"""
You are the Instagram commercial prospect classification engine.

Analyze the ACTUAL BUSINESS/PROFILE represented by this Instagram account using only the supplied evidence.
The campaign industry is the target context only. Determine the profile's ACTUAL industry independently; do not copy the campaign target into industry_detected.
Do not invent services, ownership, location, clients, partnerships or needs.
{prospecting_instruction}

============================================================
CAMPAIGN
============================================================
{json.dumps(campaign_info, ensure_ascii=False, indent=2)}

Campaign industry_target (target only): {json.dumps(industry, ensure_ascii=False)}

Available campaign services:
{json.dumps(services, ensure_ascii=False, indent=2)}

Target locations (EMPTY means NO geographic restriction):
{json.dumps((strategy.get("locations") or campaign.get("locations") or []), ensure_ascii=False, indent=2)}

============================================================
INDUSTRY COMPETITOR RULES — CURRENT RUNTIME MODEL
============================================================
{json.dumps(rules, ensure_ascii=False, indent=2)}

Use these rules to determine direct/probable competition.

============================================================
ORIGINAL COMPETITOR RULES — FULL MIGRATED SOURCE
============================================================
{original_competitor_rules}

The ORIGINAL COMPETITOR RULES are the authoritative source of the original campaign logic.
Do not discard a source rule merely because the CURRENT RUNTIME MODEL uses a compact structure.
Where both express the same rule, apply the same business meaning. Where a source rule is more
specific, preserve that specificity.

Use these rules to determine direct/probable competition. A complementary business is NOT a competitor unless it actually offers the campaign's core service.
For industries with explicit competitor categories in the rules, follow them strictly.

============================================================
LONG-FORM INDUSTRY CLASSIFICATION RULES
============================================================
When present, these are the supplied Facebook campaign rules for the same industry.
Preserve their decision logic on Instagram while using Instagram evidence fields.
Do not invent information. The campaign target does not automatically determine the
actual industry of the profile.
{long_form_rules}

============================================================
PROFILE EVIDENCE
============================================================
PROFILE:
{json.dumps(profile_context or {}, ensure_ascii=False, indent=2)}

SOURCE POST:
{json.dumps(post_context or {}, ensure_ascii=False, indent=2)}

RECENT POSTS:
{json.dumps(recent_posts or [], ensure_ascii=False, indent=2)}

============================================================
DISCOVERY HASHTAG POLICY — FULL MIGRATED SOURCE
============================================================
{discovery_policy}

A discovery hashtag is a discovery input, not proof of business location or prospect validity.
Apply the source policy's geographic and double-validation intent: the profile/business itself
must satisfy the location evidence requirement before qualification/engagement.

============================================================
GEOGRAPHIC QUALIFICATION
============================================================
If Target locations is NOT empty, geographic membership is mandatory.
Determine whether the BUSINESS/profile is actually based in, operates in, or is clearly
serving one of the target locations using only supplied evidence. A hashtag alone is
NOT proof that the business is located there. A post mentioning another city can be
important evidence of a mismatch.

Return:
- location_match=true only when the supplied evidence supports the target area with business/profile evidence. A hashtag, source_value, username fragment, tagged account, event, visit, or one-off city mention alone is NOT enough.
- location_match=false when the evidence clearly places the business outside the target area.
- location_match=null when the location cannot be verified from the supplied evidence. Use location_confidence=low for weak/indirect evidence, medium for repeated project/client evidence, and high for explicit service-area/location/address evidence.
When Target locations is empty, location_match MUST be true because there is no geographic restriction.

A personal employee account should be classified as COMMON_PERSON when the account itself
is personal and the evidence only connects it to an employer. Do not turn an employee's
personal account into a qualified business prospect merely because the employer is a relevant
industry.

============================================================
COMMERCIAL PROSPECTING
============================================================

First identify what kind of BUSINESS this is. Analyze the business, not an isolated keyword in a caption.

Use mode=normal_prospecting when the business itself could reasonably purchase one campaign service.
Use mode=b2b_referral when the business is complementary and could naturally refer customers, subcontract work,
collaborate, or support clients who need a campaign service.
Use mode=skip for direct competitors, clearly irrelevant/personal profiles, or profiles without a meaningful
commercial connection.

When mode is not skip, selected_service MUST be exactly ONE item from the campaign's Available campaign services.
Never return an array and never invent a service.

Examples of service selection:
- Realtor + marketing services + property/listing activity -> normally Lead Generation.
- Restaurant/beauty/automotive local business + marketing services -> normally Social Media Management unless
  the evidence specifically supports lead generation or paid advertising.
- Property manager + Commercial Cleaning -> b2b_referral + Commercial Cleaning.
- General contractor/landscaper + Fence Installation -> b2b_referral + Fence Installation.
- Wedding/event photographer + Digital Marketing -> b2b_referral + Social Media Management unless explicit evidence
  supports another service.

A business does NOT need to explicitly ask for the service to be a valid prospect. If there is no explicit request
but a reasonable commercial opportunity exists, request_directness=indirect.
Use direct only when the post itself explicitly requests the service/provider/recommendation/quote/help.
Use unclear when the request signal is ambiguous. Use none only when skip_post=true.

b2b_confidence is mandatory: high for a clear referral/partnership relationship, medium for a plausible but
incomplete relationship, low when there is no meaningful B2B referral relationship or the profile is skipped.

b2b_target_type should identify the partner type when b2b_referral is used (for example realtor, property_manager,
contractor, landscaper, photographer, local_business). b2b_angle should describe referral, partnership,
client_support, project_support, service_partner, or mutual_support. Leave both empty for skip.

============================================================
SKIP RULES
============================================================
- Direct competitor according to the industry rules -> skip_post=true, mode=skip.
- Clearly personal/unrelated profile -> skip_post=true, mode=skip.
- No meaningful commercial connection -> skip_post=true, mode=skip.
- Never convert a direct competitor into a referral partner.

When skip_post=true, selected_service, b2b_target_type, b2b_angle and comment MUST be empty;
b2b_confidence=low and request_directness=none.

============================================================
OUTPUT
============================================================
Return ONLY valid JSON. No markdown. No code fences. No explanation.
Return exactly these fields:
{{
  "competitor_score": 0,
  "is_competitor": false,
  "is_blacklisted": false,
  "blacklist_reason": "",
  "profile_classification": "UNKNOWN",
  "business_role": "UNKNOWN",
  "business_vertical": "UNKNOWN",
  "competitor_relation": "UNKNOWN",
  "commercial_intent_score": 0,
  "classification_confidence": 0,
  "classification_evidence": [],
  "industry_detected": "UNKNOWN",
  "location_match": null,
  "location_confidence": "low",
  "location_evidence": [],
  "skip_post": false,
  "mode": "normal_prospecting",
  "selected_service": "",
  "b2b_target_type": "",
  "b2b_angle": "",
  "b2b_confidence": "low",
  "request_directness": "indirect",
  "service_match_reason": "",
  "comment": ""
}}

ABSOLUTE RULES:
- industry_detected MUST describe the actual business/profile. It may differ from industry_target.
- competitor_score is 0-200; commercial_intent_score and classification_confidence are 0-100.
- If direct competition is established: is_competitor=true, is_blacklisted=true, competitor_relation=DIRECT_COMPETITOR,
  status is logically BLACKLISTED, and mode=skip.
- If not direct competition, is_blacklisted=false.
- selected_service must be one available campaign service whenever skip_post=false.
- IMPORTANT: the exact allowed services are ONLY the values in Available campaign services above. The long-form rules are guidance only; never substitute a service from those rules that is not in the campaign snapshot.
- If Target locations is not empty, location_match=true is required to keep skip_post=false.
- If Target locations is empty, location_match=true.
- If the location cannot be verified for a geographically restricted campaign, use location_match=null and skip_post=true.
- A personal employee account is not a business prospect; use COMMON_PERSON and skip_post=true when the evidence supports that classification.
- For a SERVICE-PROSPECTING campaign, do NOT use UNRELATED_BUSINESS merely because industry_detected differs from the campaign service/target. A non-competitor local business is eligible when it has commercial identity and location evidence.
- - If skip_post=false, comment must not be empty.
- classification_evidence and location_evidence must contain concise factual evidence only.
- commercial_intent_score must reflect the whole commercial opportunity, not keyword count:
  business/profile fit 0-25, campaign-service fit 0-25, commercial activity/intent 0-20,
  B2B/referral relationship 0-15, and evidence quality/location confidence 0-15.
  Sum those dimensions. Do not award points merely because a hashtag contains the city or industry.
- qualification_decision is an internal deterministic label: DISCARDED for skip, QUALIFIED for score >= 6
  on the 0-10 qualification scale, REVIEW for a non-skipped candidate below 6. engageable is true only for QUALIFIED candidates.
""".strip()

    # =========================================================
    # PARSER
    # =========================================================

    def parse_response(
        self,
        raw_response: Any,
    ) -> Optional[dict]:

        try:

            # -------------------------------------------------
            # Response already parsed
            # -------------------------------------------------

            if isinstance(raw_response, dict):

                response_value = raw_response.get(
                    "response"
                )

                if isinstance(
                    response_value,
                    str,
                ):
                    text = response_value

                else:
                    return raw_response

            else:
                text = str(raw_response or "")

            text = text.strip()

            if not text:
                return None

            # -------------------------------------------------
            # Remove markdown fences
            # -------------------------------------------------

            if text.startswith("```"):

                lines = text.splitlines()

                cleaned_lines = []

                for line in lines:

                    stripped = line.strip()

                    if stripped.startswith("```"):
                        continue

                    cleaned_lines.append(line)

                text = "\n".join(
                    cleaned_lines
                ).strip()

            # -------------------------------------------------
            # Extract JSON object if there is extra text
            # -------------------------------------------------

            start = text.find("{")
            end = text.rfind("}")

            if start == -1 or end <= start:
                return None

            text = text[
                start:end + 1
            ].strip()

            # -------------------------------------------------
            # JSON
            # -------------------------------------------------

            parsed = json.loads(text)

            if not isinstance(parsed, dict):
                return None

            return parsed

        except Exception as exc:

            if self.log:
                self.log.warning(
                    "[instagram-classifier] "
                    "JSON parse error=%r",
                    exc,
                )

            return None

    # =========================================================
    # NORMALIZE
    # =========================================================

    def normalize_result(
        self,
        parsed: dict,
        industry: str,
    ) -> dict:

        parsed = parsed or {}

        # -----------------------------------------------------
        # Competitor
        # -----------------------------------------------------

        raw_relation = self.normalize_text(
            parsed.get("competitor_relation")
        ).upper().replace(" ", "_")

        raw_relation = self.COMPETITOR_RELATION_ALIASES.get(
            raw_relation,
            raw_relation,
        )

        relation = self.normalize_enum(
            raw_relation,
            self.COMPETITOR_RELATIONS,
            "UNKNOWN",
        )

        # Canonical relation is what the rest of the bot persists/consumes.
        relation = self.COMPETITOR_RELATION_ALIASES.get(
            relation,
            relation,
        )

        raw_is_competitor = self.to_bool(
            parsed.get("is_competitor")
        )

        raw_blacklisted = self.to_bool(
            parsed.get("is_blacklisted")
        )

        # Direct competitor always wins.
        is_competitor = (
            relation == "DIRECT_COMPETITOR"
            or raw_is_competitor
        )

        is_blacklisted = (
            relation == "DIRECT_COMPETITOR"
            or raw_blacklisted
            or is_competitor
        )

        # If AI says competitor but relation is UNKNOWN,
        # normalize to DIRECT_COMPETITOR because the system
        # treats competitors as blacklistable.
        if is_competitor and relation == "UNKNOWN":
            relation = "DIRECT_COMPETITOR"

        # -----------------------------------------------------
        # Scores
        # -----------------------------------------------------

        competitor_score = self.clamp_int(
            parsed.get("competitor_score"),
            minimum=0,
            maximum=200,
            default=0,
        )

        commercial_intent_score = self.clamp_int(
            parsed.get(
                "commercial_intent_score"
            ),
            minimum=0,
            maximum=100,
            default=0,
        )

        confidence = self.clamp_int(
            parsed.get(
                "classification_confidence"
            ),
            minimum=0,
            maximum=100,
            default=0,
        )

        # -----------------------------------------------------
        # Classification
        # -----------------------------------------------------

        profile_classification = (
            self.normalize_enum(
                parsed.get(
                    "profile_classification"
                ),
                self.PROFILE_CLASSIFICATIONS,
                "UNKNOWN",
            )
        )

        business_role = self.normalize_enum(
            parsed.get("business_role"),
            self.BUSINESS_ROLES,
            "UNKNOWN",
        )

        business_vertical = self.normalize_enum(
            parsed.get("business_vertical"),
            self.BUSINESS_VERTICALS,
            "UNKNOWN",
        )

        # -----------------------------------------------------
        # Evidence
        # -----------------------------------------------------

        evidence = parsed.get(
            "classification_evidence"
        )

        if not isinstance(evidence, list):
            evidence = []

        evidence = [
            str(item).strip()
            for item in evidence
            if str(item).strip()
        ]

        # -----------------------------------------------------
        # Blacklist reason
        # -----------------------------------------------------

        blacklist_reason = str(
            parsed.get("blacklist_reason")
            or ""
        ).strip()

        if is_competitor and not blacklist_reason:
            blacklist_reason = (
                "Profile classified as direct competitor."
            )

        # -----------------------------------------------------
        # Industry
        # -----------------------------------------------------

        # The campaign target and the detected prospect industry are distinct.
        # Prefer the AI's actual industry; fall back to business_vertical only
        # when it is specific enough. Never silently copy the campaign target.
        raw_detected = self.normalize_text(parsed.get("industry_detected"))
        if raw_detected in {"unknown", "none", "n/a", "na"}:
            raw_detected = ""
        detected_alias = self.INDUSTRY_ALIASES.get(raw_detected)
        if detected_alias:
            raw_detected = detected_alias
        else:
            vertical_text = self.normalize_text(parsed.get("business_vertical"))
            raw_detected = self.INDUSTRY_ALIASES.get(vertical_text, vertical_text)
        industry_detected = raw_detected or "unknown"

        mode = str(parsed.get("mode") or "").strip().lower()
        if mode not in {"normal_prospecting", "b2b_referral", "skip"}:
            mode = "skip" if is_blacklisted else "normal_prospecting"

        selected_service = str(
            parsed.get("selected_service") or ""
        ).strip()
        # Services are validated later in classify(), where campaign
        # context is available.

        b2b_confidence = str(
            parsed.get("b2b_confidence") or "low"
        ).strip().lower()
        if b2b_confidence not in {"high", "medium", "low"}:
            b2b_confidence = "low"

        request_directness = str(
            parsed.get("request_directness")
            or ("none" if is_blacklisted else "indirect")
        ).strip().lower()
        if request_directness not in {"direct", "indirect", "unclear", "none"}:
            request_directness = "none" if is_blacklisted else "indirect"

        if mode == "skip" or is_blacklisted:
            selected_service = ""
            request_directness = "none"

        raw_location_match = parsed.get("location_match")
        if isinstance(raw_location_match, str):
            location_match_text = self.normalize_text(raw_location_match).lower()
            if location_match_text in {"true", "yes", "si", "sí", "match", "inside", "within", "local"}:
                location_match = True
            elif location_match_text in {"false", "no", "fuera", "outside", "mismatch", "not_match", "non_local"}:
                location_match = False
            else:
                location_match = None
        elif isinstance(raw_location_match, bool):
            location_match = raw_location_match
        else:
            location_match = None

        location_confidence = str(
            parsed.get("location_confidence") or "low"
        ).strip().lower()
        if location_confidence not in {"high", "medium", "low"}:
            location_confidence = "low"

        location_evidence = parsed.get("location_evidence")
        if not isinstance(location_evidence, list):
            location_evidence = []
        location_evidence = [
            str(item).strip()
            for item in location_evidence
            if str(item).strip()
        ]

        return {
            "competitor_score": competitor_score,

            "is_competitor": is_competitor,

            "is_blacklisted": is_blacklisted,

            "blacklist_reason": blacklist_reason,

            "profile_classification": (
                profile_classification
            ),

            "business_role": business_role,

            "business_vertical": business_vertical,

            "competitor_relation": relation,

            "commercial_intent_score": (
                commercial_intent_score
            ),

            "qualification_score": int(round(commercial_intent_score / 10.0)),
            "qualification_decision": "QUALIFIED" if commercial_intent_score >= 60 else "REVIEW",
            "engageable": commercial_intent_score >= 60,

            "classification_confidence": (
                confidence
            ),

            "classification_evidence": evidence,

            "industry_detected": industry_detected,

            "location_match": location_match,
            "location_confidence": location_confidence,
            "location_evidence": location_evidence,

            "skip_post": (
                self.to_bool(parsed.get("skip_post"))
                if "skip_post" in parsed
                else is_blacklisted
            ),
            "mode": mode,
            "selected_service": selected_service,
            "b2b_target_type": str(
                parsed.get("b2b_target_type") or ""
            ).strip(),
            "b2b_angle": str(
                parsed.get("b2b_angle") or ""
            ).strip(),
            "b2b_confidence": b2b_confidence,
            "request_directness": request_directness,
            "service_match_reason": str(
                parsed.get("service_match_reason") or ""
            ).strip(),
            "comment": str(
                parsed.get("comment") or ""
            ).strip(),
            "notes": str(
                parsed.get("notes") or ""
            ).strip(),
        }

    US_STATE_ALIASES = {
        "alabama":"al", "alaska":"ak", "arizona":"az", "arkansas":"ar", "california":"ca",
        "colorado":"co", "connecticut":"ct", "delaware":"de", "florida":"fl", "georgia":"ga",
        "illinois":"il", "indiana":"in", "iowa":"ia", "kansas":"ks", "kentucky":"ky", "louisiana":"la",
        "maine":"me", "maryland":"md", "massachusetts":"ma", "michigan":"mi", "minnesota":"mn",
        "mississippi":"ms", "missouri":"mo", "montana":"mt", "nebraska":"ne", "nevada":"nv",
        "new hampshire":"nh", "new jersey":"nj", "new mexico":"nm", "new york":"ny", "north carolina":"nc",
        "north dakota":"nd", "ohio":"oh", "oklahoma":"ok", "oregon":"or", "pennsylvania":"pa",
        "rhode island":"ri", "south carolina":"sc", "south dakota":"sd", "tennessee":"tn", "texas":"tx",
        "utah":"ut", "vermont":"vt", "virginia":"va", "washington":"wa", "west virginia":"wv",
        "wisconsin":"wi", "wyoming":"wy", "district of columbia":"dc",
    }

    @classmethod
    def _location_terms(cls, location: str) -> list[str]:
        normalized = cls.normalize_location_text(location)
        terms = []
        if normalized:
            base = normalized
            for suffix in (" metropolitan area", " metro area", " metroplex", " metropolitan"):
                if base.endswith(suffix):
                    base = base[:-len(suffix)].strip()
            terms.append(base)
            parts = base.split()
            # City/metro phrase before a state abbreviation or full state name.
            if "," in str(location):
                city = cls.normalize_location_text(str(location).split(",", 1)[0])
                if city:
                    terms.append(city)
            state_names = set(cls.US_STATE_ALIASES.keys())
            state_abbrs = set(cls.US_STATE_ALIASES.values())
            if parts and parts[-1] in state_abbrs:
                city = " ".join(parts[:-1]).strip()
                if city:
                    terms.append(city)
            else:
                for state_name in sorted(state_names, key=len, reverse=True):
                    if base.endswith(" " + state_name):
                        city = base[:-(len(state_name)+1)].strip()
                        if city:
                            terms.append(city)
                        break
        return list(dict.fromkeys(x for x in terms if x))

    @classmethod
    def _enforce_location_evidence(cls, result: dict, campaign: dict, profile_context: dict, post_context: dict, recent_posts: list[dict]) -> dict:
        locations = cls._campaign_locations_static(campaign)
        if not locations:
            result["location_match"] = True
            result["location_confidence"] = "high"
            result["location_evidence"] = list(result.get("location_evidence") or []) or ["La campaña no define restricciones geográficas."]
            return result

        profile_text = cls.normalize_location_text(" ".join(str(profile_context.get(k) or "") for k in ("display_name", "bio")))
        post_texts = [cls.normalize_location_text(str(post_context.get(k) or "")) for k in ("caption_text", "text_context", "location", "location_name")]
        recent_texts = []
        for post in recent_posts or []:
            if isinstance(post, dict):
                recent_texts.append(cls.normalize_location_text(" ".join(str(post.get(k) or "") for k in ("caption_text", "text_context", "location", "location_name"))))
        business_text = " ".join([profile_text] + post_texts + recent_texts)
        ai_evidence = [str(x) for x in (result.get("location_evidence") or []) if str(x).strip()]
        ai_text = cls.normalize_location_text(" ".join(ai_evidence))
        evidence_text = business_text + " " + ai_text

        target_terms = [term for loc in locations for term in cls._location_terms(loc)]
        target_terms = list(dict.fromkeys(target_terms))
        target_hit = any(term and term in business_text for term in target_terms)
        ai_target_hit = any(term and term in ai_text for term in target_terms)

        # Explicit business-location language is strong evidence.
        strong_patterns = ("based in", "located in", "serving", "service area", "areas we serve",
                           "headquartered", "office in", "our location", "address", "proudly serving")
        strong_target = target_hit and any(pattern in business_text for pattern in strong_patterns)
        # Two or more target references across actual business content are medium evidence.
        occurrences = sum(business_text.count(term) for term in target_terms if term)
        medium_target = target_hit and occurrences >= 2

        # AI evidence is useful only when it is corroborated by actual profile/post
        # content. Hashtags/source references alone are deliberately weak.
        weak_only = ai_target_hit and not target_hit
        if strong_target:
            result["location_match"] = True
            result["location_confidence"] = "high"
            evidence = ai_evidence[:]
            evidence.append("Perfil/publicaciones contienen evidencia explícita de operación o servicio en la zona objetivo.")
        elif medium_target:
            result["location_match"] = True
            result["location_confidence"] = "medium"
            evidence = ai_evidence[:]
            evidence.append("La zona objetivo aparece de forma repetida en contenido del perfil/publicaciones.")
        else:
            # An explicit AI mismatch backed by evidence must remain false;
            # otherwise the later heuristic would incorrectly turn a known
            # out-of-area profile into UNKNOWN.
            if result.get("location_match") is False and ai_evidence:
                result["location_match"] = False
                result["location_confidence"] = "high"
            else:
                # If the AI claims a match based on hashtag/username/source alone,
                # do not accept it as geographic proof.
                result["location_match"] = None
                result["location_confidence"] = "low"
            evidence = [x for x in ai_evidence if cls.normalize_location_text(x)]
            if weak_only or any("hashtag" in cls.normalize_location_text(x) or "source" in cls.normalize_location_text(x) or "username" in cls.normalize_location_text(x) for x in evidence):
                evidence.append("La evidencia geográfica disponible es débil (hashtag, fuente, username o mención indirecta) y no se acepta como prueba de ubicación.")
            elif target_hit:
                evidence.append("La zona aparece, pero no existe evidencia suficiente de que el negocio opere allí.")
            else:
                evidence.append("No se encontró evidencia suficiente en perfil/publicaciones para verificar la zona objetivo.")

        # Strongly documented out-of-area state/location evidence wins over a weak target mention.
        target_state_names = set()
        target_state_abbr = set()
        for loc in locations:
            n = cls.normalize_location_text(loc)
            parts = n.split()
            for name, abbr in cls.US_STATE_ALIASES.items():
                if name in n or (abbr in parts and len(abbr) == 2):
                    target_state_names.add(name); target_state_abbr.add(abbr)
        outside_states = []
        for name, abbr in cls.US_STATE_ALIASES.items():
            # Full state names are safe; short abbreviations such as "in" or
            # "or" would create false positives in normalized prose.
            if name in evidence_text:
                if name not in target_state_names and abbr not in target_state_abbr:
                    outside_states.append(name)
        if outside_states and not strong_target and not medium_target:
            result["location_match"] = False
            result["location_confidence"] = "high"
            evidence.append("El contenido del perfil/publicaciones sitúa el negocio fuera de la zona objetivo: " + ", ".join(dict.fromkeys(outside_states)) + ".")

        result["location_evidence"] = list(dict.fromkeys(evidence))[:8]
        return result

    @classmethod
    def _campaign_locations_static(cls, campaign: dict) -> list[str]:
        campaign = campaign or {}
        strategy = campaign.get("strategy_snapshot") or {}
        if not isinstance(strategy, dict):
            strategy = {}
        raw = campaign.get("locations")
        if raw is None:
            raw = strategy.get("locations")
        if not isinstance(raw, list):
            raw = [raw] if raw else []
        out, seen = [], set()
        for item in raw:
            value = str(item or "").strip()
            key = cls.normalize_location_text(value)
            if value and key and key not in seen:
                seen.add(key); out.append(value)
        return out

    # =========================================================
    # SERVICE-PROSPECTING RECOVERY
    # =========================================================

    @classmethod
    def _campaign_services_normalized(cls, campaign: dict) -> dict[str, str]:
        services = (campaign or {}).get("services_snapshot") or []
        if not isinstance(services, list):
            services = [services]
        return {
            cls.normalize_text(item): str(item).strip()
            for item in services
            if str(item or "").strip()
        }

    @classmethod
    def _infer_marketing_service(cls, result: dict, campaign: dict) -> str:
        services = cls._campaign_services_normalized(campaign)
        if not services:
            return ""

        selected = cls.normalize_text(result.get("selected_service"))
        if selected in services:
            return services[selected]

        vertical = cls.normalize_text(result.get("business_vertical"))
        industry = cls.normalize_text(result.get("industry_detected"))
        profile = cls.normalize_text(result.get("profile_classification"))

        priorities = []
        if vertical in {"real estate"} or industry in {"real estate", "realestate"}:
            priorities += ["lead generation", "online advertising", "advertising", "social media marketing", "social media management"]
        else:
            priorities += ["social media management", "social media marketing", "content marketing", "lead generation", "online advertising", "advertising", "seo", "digital marketing"]

        # For a generic local business, require evidence that it is actually
        # commercial before selecting a service. The caller supplies that gate.
        for candidate in priorities:
            if candidate in services:
                return services[candidate]

        # If the model supplied a valid service under a different spelling,
        # normalized exact matching above handles it. Never invent a service.
        return ""

    def _recover_service_prospecting_candidate(
        self,
        result: dict,
        campaign: dict,
        profile_context: dict,
        post_context: dict,
        recent_posts: list[dict],
    ) -> dict:
        """Repair an over-conservative AI skip for a clear service prospect.

        This is intentionally narrow: it only applies to marketing service
        campaigns, never to competitors, personal accounts, unrelated accounts,
        or geographically unverified profiles. The goal is to prevent the AI's
        optional `skip_post` flag from erasing strong commercial evidence.
        """
        if not self.is_service_prospecting_campaign(
            campaign, self.detect_campaign_industry(campaign)
        ):
            return result

        if result.get("is_competitor") or result.get("is_blacklisted"):
            return result

        relation = str(result.get("competitor_relation") or "UNKNOWN").upper()
        if relation in {"DIRECT_COMPETITOR", "POSSIBLE_COMPETITOR", "PERSONAL_PROFILE"}:
            return result

        if result.get("location_match") is not True:
            return result

        # For service-prospecting, UNRELATED_BUSINESS only means the prospect
        # differs from the campaign industry. That is expected when the
        # campaign sells marketing services to local businesses.
        service_prospecting_unrelated = relation == "UNRELATED_BUSINESS"

        profile_classification = str(result.get("profile_classification") or "UNKNOWN").upper()
        business_role = str(result.get("business_role") or "UNKNOWN").upper()
        if profile_classification in {"COMMON_PERSON", "PERSONAL", "EMPLOYEE"} or business_role == "EMPLOYEE":
            return result

        intent = self.clamp_int(result.get("commercial_intent_score"), 0, 100, 0)

        # Require an actual commercial identity signal. This prevents a high
        # intent value alone from turning an arbitrary profile into a prospect.
        values = [
            profile_context.get("username"),
            profile_context.get("display_name"),
            profile_context.get("bio"),
            post_context.get("caption_text"),
            post_context.get("text_context"),
        ]
        values.extend(
            p.get("caption_text") or p.get("text_context") or ""
            for p in recent_posts or []
            if isinstance(p, dict)
        )
        text = self.normalize_text(" ".join(str(v or "") for v in values))
        business_signals = tuple(self.normalize_text(x) for x in self.PROFILE_STRONG_BUSINESS_SIGNALS)
        has_business_signal = any(signal and signal in text for signal in business_signals)
        if profile_classification in {"BUSINESS", "PROFESSIONAL", "LOCAL_BUSINESS_PAGE", "LOCAL_BUSINESS_OWNER", "INDEPENDENT_NICHE_SPECIALIST"}:
            has_business_signal = True
        if business_role not in {"NONE", "UNKNOWN"}:
            has_business_signal = True
        if not has_business_signal:
            return result

        # Recover an AI under-score when the account is demonstrably a
        # commercial local business. Do not fabricate a high score: 60 is only
        # the minimum qualification threshold.
        if intent < 60:
            if service_prospecting_unrelated or profile_classification in {
                "BUSINESS",
                "PROFESSIONAL",
                "LOCAL_BUSINESS_PAGE",
                "LOCAL_BUSINESS_OWNER",
                "INDEPENDENT_NICHE_SPECIALIST",
            }:
                intent = 60
            else:
                return result

        service = self._infer_marketing_service(result, campaign)
        if not service:
            return result

        if service_prospecting_unrelated:
            result["competitor_relation"] = "UNKNOWN"

        result["skip_post"] = False
        result["mode"] = "normal_prospecting"
        result["selected_service"] = service
        result["request_directness"] = "indirect"
        result["b2b_confidence"] = "medium"
        result["commercial_intent_score"] = intent
        result["service_match_reason"] = (
            result.get("service_match_reason")
            or "Negocio comercial no competidor con presencia local y oportunidad plausible para servicios de marketing."
        )
        evidence = list(result.get("classification_evidence") or [])
        evidence.append("Se recupera como prospecto de servicios: negocio comercial local, no competidor y con intención comercial suficiente.")
        result["classification_evidence"] = list(dict.fromkeys(evidence))[:10]
        return result

    # =========================================================
    # VALIDATE RESULT
    # =========================================================

    def validate_result(
        self,
        result: dict,
        industry: str,
        campaign: Optional[dict] = None,
    ) -> dict:

        result = result or {}

        relation = result.get(
            "competitor_relation"
        )

        # Industry prompts define 60+ as blacklist territory. Keep this
        # deterministic even if the model forgets one of the boolean flags.
        if (
            relation != "PERSONAL_PROFILE"
            and result.get("competitor_score", 0) >= 60
        ):
            relation = "DIRECT_COMPETITOR"
            result["competitor_relation"] = relation
            result["is_competitor"] = True
            result["is_blacklisted"] = True

        # -----------------------------------------------------
        # DIRECT COMPETITOR
        # -----------------------------------------------------

        if relation == "DIRECT_COMPETITOR":

            result["is_competitor"] = True
            result["is_blacklisted"] = True

            if result.get(
                "competitor_score",
                0,
            ) < 150:

                result["competitor_score"] = 150

            if not result.get(
                "blacklist_reason"
            ):

                result["blacklist_reason"] = (
                    "Direct competitor."
                )

        # -----------------------------------------------------
        # POSSIBLE COMPETITOR
        # -----------------------------------------------------

        elif relation == "POSSIBLE_COMPETITOR":

            result["is_competitor"] = False
            result["is_blacklisted"] = False

            if result.get(
                "competitor_score",
                0,
            ) > 149:

                result["competitor_score"] = 149

        # -----------------------------------------------------
        # ADJACENT
        # -----------------------------------------------------

        elif relation == "ADJACENT_LOCAL_SERVICE":

            result["is_competitor"] = False
            result["is_blacklisted"] = False

        # -----------------------------------------------------
        # PERSONAL
        # -----------------------------------------------------

        elif relation == "PERSONAL_PROFILE":

            result["is_competitor"] = False
            result["is_blacklisted"] = False

            if (
                result.get(
                    "profile_classification"
                )
                == "UNKNOWN"
            ):
                result["profile_classification"] = (
                    "COMMON_PERSON"
                )

        # -----------------------------------------------------
        # UNRELATED
        # -----------------------------------------------------

        elif relation == "UNRELATED_BUSINESS":

            result["is_competitor"] = False
            result["is_blacklisted"] = False

        # -----------------------------------------------------
        # UNKNOWN
        # -----------------------------------------------------

        else:

            result["competitor_relation"] = (
                "UNKNOWN"
            )

            # Never blacklist UNKNOWN.
            result["is_competitor"] = False
            result["is_blacklisted"] = False

        # -----------------------------------------------------
        # Commercial prospecting contract
        # -----------------------------------------------------

        # A model-provided skip is authoritative. The previous implementation
        # accidentally changed skip_post=True back to False whenever mode was
        # normal_prospecting. That caused candidates such as unrelated/personal
        # profiles to be persisted as qualified.
        requested_skip = self.to_bool(result.get("skip_post"))
        mode = str(result.get("mode") or "normal_prospecting").strip().lower()

        if mode not in {"normal_prospecting", "b2b_referral", "skip"}:
            mode = "normal_prospecting"

        # Explicit semantic exclusions remain deterministic.
        if result.get("is_blacklisted"):
            requested_skip = True
        if result.get("profile_classification") in {"COMMON_PERSON", "PERSONAL", "EMPLOYEE"}:
            requested_skip = True
        if result.get("competitor_relation") == "PERSONAL_PROFILE":
            requested_skip = True
        if result.get("competitor_relation") == "UNRELATED_BUSINESS":
            requested_skip = True
        if mode == "skip":
            requested_skip = True

        # -----------------------------------------------------
        # Geographic campaign constraint
        # -----------------------------------------------------
        campaign = campaign or {}
        strategy = campaign.get("strategy_snapshot") or {}
        if not isinstance(strategy, dict):
            strategy = {}

        locations = campaign.get("locations")
        if locations is None:
            locations = strategy.get("locations")
        if not isinstance(locations, list):
            locations = [locations] if locations else []
        locations = [str(item).strip() for item in locations if str(item or "").strip()]

        if locations:
            location_match = result.get("location_match")
            if location_match is not True:
                requested_skip = True
                result["location_match"] = False if location_match is False else None
                evidence = list(result.get("location_evidence") or [])
                if location_match is False:
                    reason = (
                        "Ubicación fuera de la zona objetivo de la campaña: "
                        + ", ".join(locations)
                    )
                else:
                    reason = (
                        "No se pudo verificar que el perfil pertenezca a la zona objetivo: "
                        + ", ".join(locations)
                    )
                if reason not in evidence:
                    evidence.append(reason)
                result["location_evidence"] = evidence
        else:
            # Empty locations means the campaign has no geographic restriction.
            result["location_match"] = True
            result["location_confidence"] = "high"
            if not result.get("location_evidence"):
                result["location_evidence"] = [
                    "La campaña no define restricciones geográficas."
                ]

        # Internal decision contract: semantic validity is separate from
        # engagement eligibility. A valid prospect below the engage threshold
        # remains valid but is not engaged automatically.
        score_10 = self.clamp_int(result.get("commercial_intent_score"), 0, 100, 0) / 10.0
        score = int(round(score_10))
        result["qualification_score"] = 0 if requested_skip else score
        result["engageable"] = bool(not requested_skip and score >= 6)
        result["qualification_decision"] = "DISCARDED" if requested_skip else ("QUALIFIED" if score >= 6 else "REVIEW")

        if requested_skip:
            result["skip_post"] = True
            result["mode"] = "skip"
            result["selected_service"] = ""
            result["b2b_target_type"] = ""
            result["b2b_angle"] = ""
            result["b2b_confidence"] = "low"
            result["request_directness"] = "none"
            result["comment"] = ""
        else:
            result["skip_post"] = False
            result["mode"] = mode
            confidence = str(result.get("b2b_confidence") or "low").strip().lower()
            result["b2b_confidence"] = confidence if confidence in {"high", "medium", "low"} else "low"
            directness = str(result.get("request_directness") or "indirect").strip().lower()
            result["request_directness"] = directness if directness in {"direct", "indirect", "unclear"} else "indirect"

        # -----------------------------------------------------
        # Industry fallback
        # -----------------------------------------------------

        if not result.get("industry_detected"):
            result["industry_detected"] = "unknown"

        result["industry_target"] = industry

        return result

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def normalize_text(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        text = str(value)

        return (
            text
            .strip()
            .lower()
            .replace("_", " ")
            .replace("-", " ")
        )

    @staticmethod
    def safe_int(
        value: Any,
        default: int = 0,
    ) -> int:

        try:
            return int(float(value))

        except Exception:
            return default

    @classmethod
    def clamp_int(
        cls,
        value: Any,
        minimum: int,
        maximum: int,
        default: int = 0,
    ) -> int:

        number = cls.safe_int(
            value,
            default,
        )

        return max(
            minimum,
            min(
                maximum,
                number,
            ),
        )

    @staticmethod
    def to_bool(
        value: Any,
    ) -> bool:

        if isinstance(value, bool):
            return value

        if value is None:
            return False

        if isinstance(value, (int, float)):
            return value != 0

        normalized = (
            str(value)
            .strip()
            .lower()
        )

        return normalized in {
            "true",
            "1",
            "yes",
            "y",
            "si",
            "sí",
        }

    @staticmethod
    def normalize_enum(
        value: Any,
        allowed: set[str],
        default: str,
    ) -> str:

        if value is None:
            return default

        normalized = (
            str(value)
            .strip()
            .upper()
            .replace(" ", "_")
            .replace("-", "_")
        )

        if normalized in allowed:
            return normalized

        return default

    @staticmethod
    def infer_vertical_from_industry(
        industry: str,
    ) -> str:

        normalized = (
            str(industry or "")
            .strip()
            .lower()
        )

        mapping = {
            "cleaning": "CLEANING",
            "fences": "CONSTRUCTION",
            "botanica": "OTHER_SERVICE",
            "spa": "BEAUTY",
            "spa colombia": "BEAUTY",
            "abogados": "OTHER_SERVICE",
            "marketing": "OTHER_SERVICE",
        }

        return mapping.get(
            normalized,
            "UNKNOWN",
        )