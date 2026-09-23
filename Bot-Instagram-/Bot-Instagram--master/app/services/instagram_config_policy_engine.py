from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService


class InstagramConfigPolicyEngine:
    """Deterministic enforcement for the migrated Facebook-style JSON rules."""

    @staticmethod
    def norm(value: Any) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"\s+", " ", text.lower()).strip()
        return text

    @classmethod
    def _keywords(cls, layer: dict) -> list[str]:
        out = []
        for item in layer.get("keywords") or []:
            if isinstance(item, dict):
                word = item.get("word")
            else:
                word = item
            word = cls.norm(word)
            if word:
                out.append(word)
        return list(dict.fromkeys(out))

    @classmethod
    def _field_text(cls, layer_id: str, profile: dict, post: dict, recent: list[dict]) -> str:
        if layer_id == "L1":
            return " ".join(str(profile.get(k) or "") for k in ("username", "display_name", "profile_name", "name"))
        if layer_id == "L2":
            return " ".join(str(profile.get(k) or "") for k in ("category", "page_category", "business_category", "facebook_category", "profile_category"))
        if layer_id == "L3":
            return " ".join(str(profile.get(k) or "") for k in ("bio", "profile_description", "description"))
        if layer_id == "L4":
            parts = [str(post.get(k) or "") for k in ("caption_text", "text_context", "caption")]
            for item in recent or []:
                if isinstance(item, dict):
                    parts.extend(str(item.get(k) or "") for k in ("caption_text", "text", "caption"))
                else:
                    parts.append(str(item))
            return " ".join(parts)
        if layer_id == "L5":
            parts = [profile.get("hashtags"), post.get("hashtags")]
            for item in recent or []:
                if isinstance(item, dict):
                    parts.append(item.get("hashtags"))
            flat = []
            for p in parts:
                if isinstance(p, (list, tuple, set)):
                    flat.extend(map(str, p))
                elif p:
                    flat.append(str(p))
            return " ".join(flat)
        return ""

    @classmethod
    def evaluate_competitor(cls, campaign_type: str, profile: dict, post: dict, recent: list[dict] | None = None) -> dict:
        """Evaluate every competitor layer directly from 02_competitor_filter.json.

        The source JSON is the only authority.  L1/L2 are hard gates; L3/L4/L5
        are score/context layers whose thresholds and exceptions are read from
        runtime_rules rather than duplicated in Python.
        """
        rules = InstagramConfigRuntimeService.load(campaign_type, "02_competitor_filter.json")
        layers = rules.get("layers") or []
        rr = rules.get("runtime_rules") or {}
        recent = recent or []
        details = []
        score = 0
        blocked = False

        def hits_for(layer, text):
            return list(dict.fromkeys([kw for kw in cls._keywords(layer) if kw and kw in text]))

        def commercial_hits(text, layer):
            values = layer.get("commercial_signals") or []
            if isinstance(values, list):
                vals = []
                for v in values:
                    vals.append(cls.norm(v.get("word") if isinstance(v, dict) else v))
                return [v for v in vals if v and v in text]
            return []

        # L1: account identity/name. A single non-safe thematic keyword blocks.
        l1 = next((x for x in layers if str(x.get("id","")).upper()=="L1"), None)
        if l1:
            text = cls.norm(cls._field_text("L1", profile, post, recent))
            hits = hits_for(l1, text)
            safe = {cls.norm(x) for x in (l1.get("safe_single_terms") or [])}
            meaningful = [h for h in hits if h not in safe]
            hit = bool(meaningful)
            pts = int(l1.get("points") or 0) if hit else 0
            if hit and rr.get("layer_L1_block_if_account_name_keyword_hit", rr.get("block_immediately_if_layer_action_is_block", True)):
                blocked = True; score = max(score, pts, 60)
            details.append({"id":"L1","hit":hit,"hits":meaningful,"points":pts,"detail":f"Keywords: {', '.join(meaningful)}" if hit else "Sin señales"})

        # Cross-field fast-path exported by the source config: a clear account
        # identity signal appearing in a post together with an explicit agency/
        # offer context is also a direct competitor signal. This preserves the
        # source's fast-path behavior without reading a second config tree.
        if not blocked:
            exports = rules.get("clean_exports") or {}
            identity_signals = [cls.norm(x) for x in (exports.get("account_name_keywords") or []) if cls.norm(x)]
            post_text = cls.norm(" ".join(str(post.get(k) or "") for k in ("caption_text","text_context","caption","text")))
            recent_text = cls.norm(" ".join(str(x.get(k) or "") for x in ("caption_text","text_context","caption","text") if isinstance(x,dict) for k in [k]))
            request = any(x in post_text for x in ("looking for", "need a", "need an", "seeking", "hiring", "wanted", "recommend a", "busco", "buscando", "necesito", "contratar", "recomendacion"))
            offer = any(x in post_text for x in ("agency", "we offer", "we provide", "our services", "helping brands", "help businesses", "clients", "services"))
            cross = [x for x in identity_signals if x in post_text]
            if cross and offer and not request:
                blocked=True; score=max(score,60)
                details.append({"id":"FAST_PATH","hit":True,"hits":cross,"points":60,"detail":"Source clean_exports identity signal + offer context"})

        # L2: official category. Clear categories block; broad review categories
        # only review when no stronger identity/content evidence exists.
        l2 = next((x for x in layers if str(x.get("id","")).upper()=="L2"), None)
        if l2 and not blocked:
            text = cls.norm(cls._field_text("L2", profile, post, recent))
            hits = hits_for(l2, text)
            review_items = l2.get("review_keywords") or []
            review_words = {cls.norm(x.get("word") if isinstance(x,dict) else x) for x in review_items}
            review_hits = [w for w in review_words if w and w in text]
            hits = list(dict.fromkeys(hits + review_hits))
            clear = [h for h in hits if h not in review_words]
            broad = [h for h in hits if h in review_words]
            pts = 0
            if clear and rr.get("layer_L2_block_if_category_is_astrologer_psychic_tarot_vidente", True):
                pts = max(int(l2.get("points") or 60), 60); blocked = True; score = max(score, pts)
            elif broad and rr.get("layer_L2_review_if_category_in_review_list", True):
                pts = int(rr.get("layer_L2_review_category_points", 35)); score += pts
            details.append({"id":"L2","hit":bool(hits),"hits":hits,"points":pts,"detail":f"Clear: {', '.join(clear)}; Review: {', '.join(broad)}" if hits else "Sin señales"})

        # L3: bio/description. Two thematic hits block; one is a review score.
        l3 = next((x for x in layers if str(x.get("id","")).upper()=="L3"), None)
        if l3 and not blocked:
            text = cls.norm(cls._field_text("L3", profile, post, recent))
            hits = hits_for(l3, text)
            commercial = commercial_hits(text, l3)
            pts = 0
            threshold = int(rr.get("layer_L3_block_if_keyword_hits_gte", 999))
            # Some source configs (notably Botanica) distinguish a single
            # *mystic identity* signal in the bio from a generic thematic
            # keyword.  That rule is independent of the generic L3 threshold
            # and must block even when there is only one matching keyword.
            mystic_identity_threshold = rr.get("layer_L3_block_if_mystic_identity_keyword_hits_gte")
            mystic_identity_hits = []
            if mystic_identity_threshold is not None:
                exports = rules.get("clean_exports") or {}
                # The source's identity vocabulary is the explicit
                # account_name_keywords export. Do not treat every bio
                # keyword as identity: phrases such as "contenido espiritual"
                # are thematic signals and remain subject to the generic L3
                # threshold.
                identity_words = [cls.norm(x) for x in (exports.get("account_name_keywords") or []) if cls.norm(x)]
                mystic_identity_hits = [h for h in identity_words if h in text]
            if mystic_identity_threshold is not None and len(mystic_identity_hits) >= int(mystic_identity_threshold):
                pts = max(int(l3.get("points") or 40), 60)
                blocked = True
                score = max(score, pts)
            elif len(hits) >= threshold:
                pts = int(l3.get("points") or 40) * max(1, len(hits))
                blocked = True
            elif hits:
                pts = int(rr.get("layer_L3_single_keyword_without_commercial_signal_points", l3.get("points") or 40))
                if commercial and rr.get("layer_L3_block_if_service_keyword_and_commercial_signal"):
                    pts += int(rr.get("commercial_signal_boost_points", 20)); blocked = pts >= int(rr.get("block_if_score_gte",60))
                score += pts
            details.append({"id":"L3","hit":bool(hits or mystic_identity_hits),"hits":hits,"mystic_identity_hits":mystic_identity_hits,"commercial_hits":commercial,"points":pts,"detail":f"Keywords: {', '.join(hits)}" if hits else "Sin señales"})

        # L4: each recent/current post is an independent recurrence signal.
        l4 = next((x for x in layers if str(x.get("id","")).upper()=="L4"), None)
        if l4 and not blocked:
            posts = [post] + [x for x in recent if isinstance(x,dict)]
            info = []
            for item in posts:
                text = cls.norm(" ".join(str(item.get(k) or "") for k in ("caption_text","text_context","caption","text")))
                ih = []
                for raw in l4.get("informational_competitor_signals") or []:
                    w=cls.norm(raw); ih.append(w) if w and w in text and w not in ih else None
                ch = commercial_hits(text,l4)
                if ih: info.append({"hits":ih,"commercial":ch})
            n=len(info); pts=0
            threshold=int(rr.get("layer_L4_block_if_keyword_hits_gte",999))
            if n >= threshold or n >= int(rr.get("layer_L4_block_if_informational_competitor_posts_gte",999)):
                pts=int(l4.get("points") or 35); blocked=True; score=max(score,60)
            elif n:
                pts=int(l4.get("points") or 35); score += pts
                if any(x["commercial"] for x in info) and rr.get("layer_L4_block_if_service_posts_with_commercial_signal_gte"):
                    blocked=True; score=max(score,60)
            details.append({"id":"L4","hit":bool(info),"posts":info,"points":pts,"detail":f"Publicaciones temáticas: {n}"})

        # L5: hashtags are only blocking when the profile/post context is also
        # thematic, as explicitly required by the source config.
        l5 = next((x for x in layers if str(x.get("id","")).upper()=="L5"), None)
        if l5 and not blocked:
            text = cls.norm(cls._field_text("L5", profile, post, recent))
            hits = hits_for(l5, text)
            profile_context = cls.norm(cls._field_text("L1", profile, post, recent) + " " + cls._field_text("L3", profile, post, recent))
            content_context = cls.norm(cls._field_text("L4", profile, post, recent))
            thematic_context = any(x in profile_context or x in content_context for x in hits)
            threshold=int(rr.get("layer_L5_block_if_keyword_hits_gte",999))
            pts=0
            if len(hits) >= threshold and (not rr.get("layer_L5_requires_context_for_block") or thematic_context):
                pts=int(l5.get("points") or 25); blocked=True; score=max(score,60)
            elif hits:
                pts=int(l5.get("points") or 25); score += pts
            details.append({"id":"L5","hit":bool(hits),"hits":hits,"context_match":thematic_context,"points":pts,"detail":f"Hashtags: {', '.join(hits)}" if hits else "Sin señales"})

        score = min(200, max(0, int(score)))
        block_threshold = int(rr.get("block_if_score_gte",60))
        review_range = rr.get("review_if_score_between") or [30,59]
        if score >= block_threshold: blocked=True
        review = (not blocked and len(review_range)>=2 and int(review_range[0]) <= score <= int(review_range[1]))
        return {
            "competitor_score": score,
            "is_competitor": bool(blocked), "is_blacklisted": bool(blocked),
            "competitor_relation": "DIRECT_COMPETITOR" if blocked else ("UNKNOWN" if review else "ADJACENT_LOCAL_SERVICE"),
            "decision": "BLOCK" if blocked else ("REVIEW" if review else "SAFE"),
            "review_required": bool(review), "layers": details,
            "blacklist_reason": "Deterministic competitor layer matched source configuration." if blocked else "",
        }

    @classmethod
    def enforce_registry_rules(cls, campaign_type: str, text: str, profile: dict | None = None, post: dict | None = None) -> dict:
        rr = InstagramConfigRuntimeService.runtime_rules(campaign_type)
        t = cls.norm(text)
        reasons: list[str] = []
        human = False
        skip = False
        urgent = False

        if rr.get("never_give_legal_advice") and any(x in t for x in ("debes demandar", "haz esto legalmente", "mi consejo legal", "te recomiendo demandar", "que hago legalmente")):
            reasons.append("legal_advice")
        if rr.get("never_request_sensitive_case_details_publicly") and any(x in t for x in ("cedula", "numero de expediente", "expediente completo", "contraseña", "direccion exacta")):
            reasons.append("sensitive_case_details")
        if rr.get("human_escalation_if_specific_strategy_requested") and any(x in t for x in ("estrategia para mi caso", "que debo hacer en mi caso", "como debo demandar", "paso a paso de mi caso")):
            human = True; reasons.append("specific_legal_strategy")
        if any(x in t for x in map(cls.norm, rr.get("urgent_terms") or [])):
            urgent = True; human = True; reasons.append("urgent_legal_term")

        if rr.get("never_give_medical_advice") and any(x in t for x in ("que dosis", "suspende el medicamento", "que tratamiento debo", "toma esta dosis")):
            reasons.append("medical_advice"); human = bool(rr.get("human_escalation_if_medical_question_requested"))
        if rr.get("never_diagnose_publicly") and any(x in t for x in ("tengo cancer", "tienes cancer", "estoy embarazada", "estas embarazada", "tengo depresion", "tienes depresion", "diagnostico")):
            reasons.append("medical_diagnosis"); human = bool(rr.get("human_escalation_if_medical_question_requested"))
        if rr.get("never_comment_on_negative_body_image_posts") and any(x in t for x in ("soy gorda", "soy gordo", "eres gorda", "eres gordo", "odio mi cuerpo", "mi cuerpo esta mal", "deberia bajar de peso")):
            reasons.append("negative_body_image"); skip = True
        if rr.get("skip_if_health_distress_or_eating_disorder_signals") and any(x in t for x in ("no quiero comer", "me provoco vomito", "me provoco el vomito", "me doy atracones", "me siento horrible con mi cuerpo", "quiero dejar de comer")):
            reasons.append("health_distress_or_eating_disorder_signal"); skip = True; human = True

        return {"blocked": bool(reasons), "reasons": sorted(set(reasons)), "human_escalation": human, "skip_post": skip, "urgent": urgent}
