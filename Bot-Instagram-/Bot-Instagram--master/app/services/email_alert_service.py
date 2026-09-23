import os
import smtplib
import ssl
import logging
from email.message import EmailMessage


class EmailAlertService:
    def __init__(self, logger=None):
        self.log = logger or logging.getLogger(self.__class__.__name__)

        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_username)
        self.smtp_use_tls = str(os.getenv("SMTP_USE_TLS", "true")).strip().lower() == "true"
        self.smtp_use_ssl = str(os.getenv("SMTP_USE_SSL", "false")).strip().lower() == "true"

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        try:
            to_email = str(to_email or "").strip()
            subject = str(subject or "").strip()
            body = str(body or "").strip()

            if not to_email:
                self.log.warning("send_email sin destinatario.")
                return False

            if not self.smtp_host or not self.smtp_username or not self.smtp_password:
                self.log.warning(
                    "Faltan credenciales SMTP. Revisa SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD."
                )
                return False

            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self.smtp_from_email
            msg["To"] = to_email
            msg.set_content(body)

            if self.smtp_use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.ehlo()
                    if self.smtp_use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                        server.ehlo()

                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)

            self.log.info("Correo enviado correctamente a %s", to_email)
            return True

        except Exception as e:
            self.log.exception("Error enviando correo: %s", e)
            return False