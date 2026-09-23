from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from app.api.prospecting_api import ProspectingAPI
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService


class InstagramProspectNoResponseTask:
    """Moves commented prospects to NO_RESPONSE after the configured reply window."""

    def __init__(self, data: dict | None = None):
        self.data = data or {}
        self.log = logging.getLogger(self.__class__.__name__)
        self.prospecting_api = ProspectingAPI()

    @staticmethod
    def _parse_dt(value):
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None

    def execute(self) -> bool:
        campaign_id = self.data.get("campaign_id")
        if not campaign_id:
            self.log.warning("campaign_id es requerido en InstagramProspectNoResponseTask")
            return False

        ok_campaign, campaign = self.prospecting_api._get(f"prospecting/campaigns/{campaign_id}/")[:2]
        if not ok_campaign or not isinstance(campaign, dict):
            # Some installations don't expose a campaign detail endpoint; the caller can pass campaign_type.
            campaign = {"campaign_type": self.data.get("campaign_type") or "botanica"}

        campaign_type = InstagramConfigRuntimeService.campaign(
            campaign.get("campaign_type") or campaign.get("industry_target") or campaign.get("industry") or self.data.get("campaign_type") or "botanica"
        )
        if not InstagramConfigRuntimeService.likes_only_after_no_response(campaign_type):
            return False
        window = InstagramConfigRuntimeService.reply_window_hours(campaign_type, 72)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window)

        ok_posts, posts = self.prospecting_api._get(
            "prospecting/prospect-posts/",
            params={"campaign_id": campaign_id, "status": "commented"},
        )[:2]
        if not ok_posts or not isinstance(posts, list):
            return False

        changed = 0
        for post in posts:
            commented_at = self._parse_dt(post.get("commented_at"))
            if not commented_at or commented_at > cutoff:
                continue
            post_id = post.get("id")
            prospect_id = post.get("prospect")
            if not post_id or not prospect_id:
                continue
            self.prospecting_api.update_prospect_post(
                post_id,
                status="no_response",
                no_response_at=datetime.now(timezone.utc).isoformat(),
            )
            self.prospecting_api.update_prospect(
                prospect_id,
                status="no_response",
            )
            changed += 1

        self.log.info("[no-response] campaign=%s transitioned=%s", campaign_id, changed)
        return changed > 0
