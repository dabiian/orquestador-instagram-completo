import logging
from app.api.prospecting_api import ProspectingAPI
from app.services.email_alert_service import EmailAlertService


class ProspectFollowUpAlertTask:
    """
    Envía alerta por correo cuando un prospecto respondió con interés o pregunta.
    Evita duplicados por interaction_id.
    """

    def __init__(self, data: dict):
        self.data = data or {}
        self.log = logging.getLogger(self.__class__.__name__)
        self.prospecting_api = ProspectingAPI()
        self.email_service = EmailAlertService(logger=self.log)

    def execute(self) -> bool:
        try:
            campaign_id = self.data.get("campaign_id")
            email_to = self.data.get("email_to") or "programadorazteca08@gmail.com"

            if not campaign_id:
                self.log.warning("campaign_id es requerido en FollowUpAlertTask")
                return False

            ok_posts, posts = self.prospecting_api._get(
                "prospecting/prospect-posts/",
                params={
                    "campaign_id": campaign_id,
                    "status": "follow_up_pending",
                },
            )[:2]

            if not ok_posts or not isinstance(posts, list) or not posts:
                self.log.warning("No hay posts en follow_up_pending.")
                return False

            sent_count = 0

            for post in posts:
                try:
                    post_id = post.get("id")
                    prospect_id = post.get("prospect")
                    post_url = str(post.get("post_url") or "").strip()

                    if not post_id or not prospect_id:
                        continue

                    latest_interaction = self._get_latest_relevant_inbound_interaction(post_id)
                    if not latest_interaction:
                        continue

                    interaction_id = latest_interaction.get("id")
                    classification = str(latest_interaction.get("classification") or "").strip().lower()
                    content_text = str(latest_interaction.get("content_text") or "").strip()

                    if not interaction_id or classification not in {"interested", "question"}:
                        continue

                    if self._already_alerted(interaction_id, email_to):
                        self.log.info(
                            "Ya existe alerta enviada/registrada para interaction_id=%s",
                            interaction_id,
                        )
                        continue

                    prospect = self._get_prospect(prospect_id)
                    if not prospect:
                        continue

                    subject = self._build_subject(prospect, classification)
                    body = self._build_body(
                        prospect=prospect,
                        post=post,
                        interaction=latest_interaction,
                    )

                    sent_ok = self.email_service.send_email(
                        to_email=email_to,
                        subject=subject,
                        body=body,
                    )

                    if not sent_ok:
                        self.log.warning(
                            "No se pudo enviar correo para interaction_id=%s",
                            interaction_id,
                        )
                        continue

                    ok_alert, alert = self.prospecting_api.create_follow_up_alert(
                        prospect_id=prospect_id,
                        prospect_post_id=post_id,
                        interaction_id=interaction_id,
                        alert_type="email",
                        status="pending",
                        email_to=email_to,
                        payload_json={
                            "reason": "Prospecto respondió con interés o pregunta",
                            "reply_text": content_text,
                            "classification": classification,
                            "delivery": "sent",
                        },
                    )

                    if not ok_alert:
                        self.log.warning(
                            "Correo enviado pero no se pudo registrar follow_up_alert para interaction_id=%s",
                            interaction_id,
                        )

                    try:
                        self.prospecting_api.create_prospect_interaction(
                            prospect_id=prospect_id,
                            prospect_post_id=post_id,
                            interaction_type="email_alerted",
                            direction="outbound",
                            content_text=f"Email alert sent to {email_to}",
                            classification=classification,
                            status="success",
                        )
                    except Exception as e:
                        self.log.warning(
                            "No se pudo registrar interaction email_alerted: %r",
                            e,
                        )

                    sent_count += 1

                except Exception as e:
                    self.log.exception("Error procesando post en FollowUpAlertTask: %s", e)
                    continue

            self.log.info("FollowUpAlertTask finalizado | correos_enviados=%s", sent_count)
            return sent_count > 0

        except Exception as e:
            self.log.exception("Error en ProspectFollowUpAlertTask: %s", e)
            return False

    def _get_latest_relevant_inbound_interaction(self, post_id: int):
        try:
            ok, interactions = self.prospecting_api._get(
                "prospecting/prospect-interactions/",
                params={
                    "prospect_post_id": post_id,
                    "direction": "inbound",
                },
            )[:2]

            if not ok or not isinstance(interactions, list) or not interactions:
                return None

            filtered = [
                item for item in interactions
                if str(item.get("interaction_type") or "").strip() == "reply_received"
                and str(item.get("classification") or "").strip().lower() in {"interested", "question"}
            ]

            if not filtered:
                return None

            filtered.sort(
                key=lambda x: str(x.get("created_at") or ""),
                reverse=True,
            )
            return filtered[0]

        except Exception:
            return None

    def _already_alerted(self, interaction_id: int, email_to: str) -> bool:
        try:
            ok, alerts = self.prospecting_api._get(
                "prospecting/follow-up-alerts/",
                params={
                    "interaction_id": interaction_id,
                },
            )[:2]

            if not ok or not isinstance(alerts, list):
                return False

            email_to_norm = str(email_to or "").strip().lower()

            for item in alerts:
                item_email = str(item.get("email_to") or "").strip().lower()
                if item_email == email_to_norm:
                    return True

            return False

        except Exception:
            return False

    def _get_prospect(self, prospect_id: int):
        try:
            ok, prospect = self.prospecting_api._get(
                f"prospecting/prospects/{prospect_id}/"
            )[:2]

            if ok and isinstance(prospect, dict):
                return prospect

            return None

        except Exception:
            return None

    def _build_subject(self, prospect: dict, classification: str) -> str:
        username = str(prospect.get("username") or "unknown").strip()
        classification = classification.lower()

        if classification == "question":
            return f"[Instagram] Prospecto pidió información: {username}"

        return f"[Instagram] Prospecto interesado: {username}"

    def _build_body(self, prospect: dict, post: dict, interaction: dict) -> str:
        username = str(prospect.get("username") or "").strip()
        profile_url = str(prospect.get("profile_url") or "").strip()
        display_name = str(prospect.get("display_name") or "").strip()
        bio = str(prospect.get("bio") or "").strip()

        post_url = str(post.get("post_url") or "").strip()
        post_caption = str(post.get("caption_text") or "").strip()

        reply_text = str(interaction.get("content_text") or "").strip()
        classification = str(interaction.get("classification") or "").strip()
        created_at = str(interaction.get("created_at") or "").strip()

        parts = [
            "Se detectó un prospecto con interés desde Instagram.",
            "",
            f"Username: {username}",
            f"Display name: {display_name}",
            f"Profile URL: {profile_url}",
            f"Classification: {classification}",
            f"Fecha interacción: {created_at}",
            "",
            f"Reply del prospecto: {reply_text}",
            "",
            f"Post URL: {post_url}",
            f"Caption del post: {post_caption}",
            "",
            f"Bio del prospecto: {bio}",
        ]

        return "\n".join(parts)