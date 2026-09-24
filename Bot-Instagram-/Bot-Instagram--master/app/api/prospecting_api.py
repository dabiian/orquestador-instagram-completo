import json
import os

import requests
from dotenv import load_dotenv

from app.utils.logger import get_logger

load_dotenv()


def _normalize_api_url(value: str) -> str:
    """
    Normaliza la URL base de la API.

    Local:
        http://localhost:8000/api/

    Docker:
        http://backend:8000/api/
    """
    value = (value or "").strip()

    if not value:
        value = "http://localhost:8000/api/"

    value = value.rstrip("/")

    if not value.endswith("/api"):
        value = value + "/api"

    return value.rstrip("/") + "/"


def _normalize_qualification_score(value) -> int:
    """Backend field is an integer 0-10 derived from the classifier's 0-100 score."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if number != number or number in (float("inf"), float("-inf")):
        return 0
    return max(0, min(10, int(round(number))))


class ProspectingAPI:
    """
    Cliente para consumir endpoints de prospectación del backend.

    La campaña se crea manualmente.
    El bot solo:
    - lee campaña activa
    - crea/consulta prospectos
    - crea/consulta posts
    - crea interacciones
    - crea alertas
    """

    def __init__(self):
        env_url = (
            os.getenv("PROSPECTING_API_URL")
            or os.getenv("TASK_API_URL")
            or os.getenv("BACKEND_API_URL")
            or os.getenv("API_BASE_URL")
            or os.getenv("BACKEND_BASE_URL")
            or os.getenv("API_URL")
            or "http://localhost:8000/api/"
        )

        self.url = _normalize_api_url(env_url)
        self.log = get_logger(self.__class__.__name__)

        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        print("[ProspectingAPI] Conectada a:", self.url)

    # =========================================================
    # HELPERS
    # =========================================================

    def _safe_json(self, response):
        try:
            return response.json()
        except Exception:
            return {"raw_text": response.text}

    def _get(self, endpoint, params=None, timeout=30):
        try:
            response = requests.get(
                self.url + endpoint,
                headers={"accept": "application/json"},
                params=params,
                timeout=timeout,
            )
            return (
                response.status_code in (200, 201),
                self._safe_json(response),
                response.status_code,
            )
        except Exception as e:
            return False, {"error": str(e)}, 0

    def _post(self, endpoint, payload, timeout=30):
        try:
            response = requests.post(
                self.url + endpoint,
                headers=self.headers,
                json=payload,
                timeout=timeout,
            )
            return (
                response.status_code in (200, 201),
                self._safe_json(response),
                response.status_code,
            )
        except Exception as e:
            return False, {"error": str(e)}, 0

    def _patch(self, endpoint, payload, timeout=30):
        try:
            response = requests.patch(
                self.url + endpoint,
                headers=self.headers,
                json=payload,
                timeout=timeout,
            )
            return (
                response.status_code in (200, 202),
                self._safe_json(response),
                response.status_code,
            )
        except Exception as e:
            return False, {"error": str(e)}, 0

    # =========================================================
    # CAMPAIGN
    # =========================================================

    def get_active_campaign(self, social_media_account_id, platform="instagram"):
        """
        Obtiene la campaña activa asignada a una cuenta específica.

        Nuevo backend:
        GET prospecting/campaigns/active/?social_media_account_id=ID&platform=instagram

        Respuesta esperada:
        {
            "ok": true,
            "campaign": {...},
            "assignment": {...}
        }
        """
        ok, data, status = self._get(
            "prospecting/campaigns/active/",
            params={
                "social_media_account_id": social_media_account_id,
                "platform": platform,
            },
        )

        if not ok:
            return False, data

        if isinstance(data, dict):
            if data.get("ok") is True and isinstance(data.get("campaign"), dict):
                campaign = dict(data["campaign"])
                if isinstance(data.get("assignment"), dict):
                    campaign["_assignment"] = dict(data["assignment"])
                return True, campaign

            if isinstance(data.get("campaign"), dict):
                campaign = dict(data["campaign"])
                if isinstance(data.get("assignment"), dict):
                    campaign["_assignment"] = dict(data["assignment"])
                return True, campaign

        return False, {
            "error": "No active campaign found",
            "response": data,
            "status": status,
        }

    def get_assignment_usage(self, assignment_id):
        """Read optional per-account prospect limits and current usage.

        daily_limit/total_limit may be null. Null explicitly means that no
        finite limit was configured for that dimension.
        """
        if not assignment_id:
            return False, {"error": "assignment_id is required"}
        return self._get(f"prospecting/campaign-accounts/{int(assignment_id)}/usage/")[:2]

    # =========================================================
    # PROSPECTS
    # =========================================================

    def find_prospect_by_username(self, campaign_id, username, platform="instagram"):
        ok, data, status = self._get(
            "prospecting/prospects/",
            params={
                "campaign_id": campaign_id,
                "platform": platform,
                "username": username,
            },
        )

        if not ok:
            return False, data

        if isinstance(data, list) and data:
            return True, data[0]

        return False, {"error": "Prospect not found"}

    def create_prospect(
        self,
        campaign_id,
        platform,
        username,
        profile_url,
        display_name="",
        bio="",
        industry_detected="",
        source_type="keyword",
        source_value="",
        status="new",
        qualification_score=0,
        qualification_reason="",
    ):
        qualification_score = _normalize_qualification_score(qualification_score)
        payload = {
            "campaign": campaign_id,
            "platform": platform,
            "username": username,
            "profile_url": profile_url,
            "display_name": display_name,
            "bio": bio,
            "industry_detected": industry_detected,
            "source_type": source_type,
            "source_value": source_value,
            "status": status,
            "qualification_score": qualification_score,
            "qualification_reason": qualification_reason,
        }

        return self._post("prospecting/prospects/", payload)[:2]

    def update_prospect(self, prospect_id, **fields):
        fields = dict(fields or {})
        if "qualification_score" in fields:
            fields["qualification_score"] = _normalize_qualification_score(fields["qualification_score"])
        return self._patch(f"prospecting/prospects/{prospect_id}/", fields)[:2]

    def update_prospect_metadata(self, prospect_id, metadata: dict) -> tuple[bool, object]:
        """Persist the rich classifier fields when the backend supports them.

        Older backends only know the legacy prospect fields. In that case a
        400/404 must not break discovery; the legacy prospect has already been
        saved and remains usable.
        """
        if not prospect_id or not isinstance(metadata, dict) or not metadata:
            return False, None
        try:
            ok, data = self.update_prospect(prospect_id, **metadata)
            if ok:
                return True, data
            self.log.warning("[prospecting] backend rechazó metadata extendida; se conserva el formato legacy | prospect_id=%s", prospect_id)
            return False, data
        except Exception as exc:
            self.log.warning("[prospecting] no se pudo guardar metadata extendida | prospect_id=%s | error=%r", prospect_id, exc)
            return False, exc

    def get_or_create_prospect(
        self,
        campaign_id,
        platform,
        username,
        profile_url,
        display_name="",
        bio="",
        industry_detected="",
        source_type="keyword",
        source_value="",
        status="new",
        qualification_score=0,
        qualification_reason="",
    ):
        ok_find, found = self.find_prospect_by_username(
            campaign_id=campaign_id,
            username=username,
            platform=platform,
        )

        if ok_find:
            prospect_id = found.get("id")

            normalized_score = _normalize_qualification_score(qualification_score)
            lifecycle_statuses = {"no_response", "human_takeover", "interested", "closed", "blacklisted"}
            existing_status = str(found.get("status") or "").strip().lower()
            preserved_status = existing_status if existing_status in lifecycle_statuses else status
            update_fields = {
                "profile_url": profile_url,
                "display_name": display_name,
                "bio": bio,
                "industry_detected": industry_detected,
                "source_type": source_type,
                "source_value": source_value,
                "status": preserved_status,
                "qualification_score": normalized_score,
                "qualification_reason": qualification_reason,
            }

            ok_update, updated = self.update_prospect(
                prospect_id,
                **update_fields,
            )

            if ok_update:
                return True, updated, False

            return False, updated, False

        ok_create, created = self.create_prospect(
            campaign_id=campaign_id,
            platform=platform,
            username=username,
            profile_url=profile_url,
            display_name=display_name,
            bio=bio,
            industry_detected=industry_detected,
            source_type=source_type,
            source_value=source_value,
            status=status,
            qualification_score=qualification_score,
            qualification_reason=qualification_reason,
        )

        return ok_create, created, True
    # =========================================================
    # PROSPECT POSTS
    # =========================================================

    def find_prospect_post_by_url(self, prospect_id, post_url):
        ok, data, status = self._get(
            "prospecting/prospect-posts/",
            params={
                "prospect_id": prospect_id,
            },
        )

        if not ok:
            return False, data

        if isinstance(data, list):
            for item in data:
                if str(item.get("post_url") or "").strip() == str(post_url).strip():
                    return True, item

        return False, {"error": "Prospect post not found"}

    def create_prospect_post(
        self,
        prospect_id,
        post_url,
        post_type="post",
        caption_text="",
        analysis_status="pending",
        is_relevant=None,
        analysis_reason="",
        status="new",
        commented_at=None,
        last_comment_text="",
    ):
        payload = {
            "prospect": prospect_id,
            "post_url": post_url,
            "post_type": post_type,
            "caption_text": caption_text,
            "analysis_status": analysis_status,
            "is_relevant": is_relevant,
            "analysis_reason": analysis_reason,
            "status": status,
            "commented_at": commented_at,
            "last_comment_text": last_comment_text,
        }

        return self._post("prospecting/prospect-posts/", payload)[:2]

    def update_prospect_post(self, prospect_post_id, **fields):
        return self._patch(f"prospecting/prospect-posts/{prospect_post_id}/", fields)[:2]

    def get_or_create_prospect_post(
        self,
        prospect_id,
        post_url,
        post_type="post",
        caption_text="",
        analysis_status="pending",
        is_relevant=None,
        analysis_reason="",
        status="new",
        commented_at=None,
        last_comment_text="",
    ):
        ok_find, found = self.find_prospect_post_by_url(
            prospect_id=prospect_id,
            post_url=post_url,
        )

        if ok_find:
            prospect_post_id = found.get("id")

            existing_status = str(found.get("status") or "").strip().lower()
            lifecycle_statuses = {"commented", "no_response", "follow_up_pending", "human_takeover"}
            preserved_status = existing_status if existing_status in lifecycle_statuses else status
            update_fields = {
                "post_type": post_type,
                "caption_text": caption_text,
                "analysis_status": analysis_status,
                "is_relevant": is_relevant,
                "analysis_reason": analysis_reason,
                "status": preserved_status,
                "commented_at": found.get("commented_at") if existing_status in lifecycle_statuses else commented_at,
                "last_comment_text": found.get("last_comment_text") if existing_status in lifecycle_statuses else last_comment_text,
            }

            ok_update, updated = self.update_prospect_post(
                prospect_post_id,
                **update_fields,
            )

            if ok_update:
                return True, updated, False

            return False, updated, False

        ok_create, created = self.create_prospect_post(
            prospect_id=prospect_id,
            post_url=post_url,
            post_type=post_type,
            caption_text=caption_text,
            analysis_status=analysis_status,
            is_relevant=is_relevant,
            analysis_reason=analysis_reason,
            status=status,
            commented_at=commented_at,
            last_comment_text=last_comment_text,
        )

        return ok_create, created, True
    # =========================================================
    # INTERACTIONS
    # =========================================================

    def create_prospect_interaction(
        self,
        prospect_id,
        interaction_type,
        direction="outbound",
        prospect_post_id=None,
        content_text="",
        classification=None,
        status="success",
        social_media_account_id=None,
    ):
        """
        Crea una interacción de prospectación.

        social_media_account_id:
        - permite saber qué cuenta hizo la acción.
        - se envía como "social_media_account" porque así lo espera DRF.
        """
        payload = {
            "prospect": prospect_id,
            "prospect_post": prospect_post_id,
            "interaction_type": interaction_type,
            "direction": direction,
            "content_text": content_text,
            "classification": classification,
            "status": status,
        }

        if social_media_account_id is not None:
            payload["social_media_account"] = social_media_account_id

        return self._post("prospecting/prospect-interactions/", payload)[:2]

    # =========================================================
    # ALERTS
    # =========================================================

    def create_follow_up_alert(
        self,
        prospect_id,
        alert_type="email",
        status="pending",
        prospect_post_id=None,
        interaction_id=None,
        email_to=None,
        payload_json=None,
    ):
        payload = {
            "prospect": prospect_id,
            "prospect_post": prospect_post_id,
            "interaction": interaction_id,
            "alert_type": alert_type,
            "status": status,
            "email_to": email_to,
            "payload_json": payload_json or {},
        }

        return self._post("prospecting/follow-up-alerts/", payload)[:2]

    def get_pending_follow_up_alerts(self):
        return self._get("prospecting/follow-up-alerts/pending/")[:2]