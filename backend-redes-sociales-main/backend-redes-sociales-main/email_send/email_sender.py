import base64
import os
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable, Optional

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"


def _load_credentials():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        else:
            creds = None

    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE),
            SCOPES,
        )
        creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w", encoding="utf-8") as token:
        token.write(creds.to_json())

    return creds


def get_gmail_service():
    """
    Crea el cliente autenticado de Gmail API.
    - Si existe token.json, intenta reutilizarlo.
    - Si expiró pero tiene refresh token, lo refresca.
    - Si no existe, abre el flujo OAuth local y luego guarda token.json.
    """
    creds = _load_credentials()

    service = build("gmail", "v1", credentials=creds)
    return service


def _normalize_recipients(to_emails: Iterable[str] | str) -> str:
    if isinstance(to_emails, str):
        return to_emails
    return ", ".join(email.strip() for email in to_emails if email.strip())


def create_message(
    sender_email: str,
    sender_name: Optional[str],
    to_emails: Iterable[str] | str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
):
    """
    Crea el MIME email y lo devuelve en formato raw base64url,
    que es lo que exige Gmail API.
    """
    to_header = _normalize_recipients(to_emails)

    if html_body:
        message = MIMEMultipart("alternative")
        message.attach(MIMEText(text_body, "plain", "utf-8"))
        message.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        message = MIMEText(text_body, "plain", "utf-8")

    if sender_name:
        message["From"] = f"{sender_name} <{sender_email}>"
    else:
        message["From"] = sender_email

    message["To"] = to_header
    message["Subject"] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return {"raw": raw_message}


def send_message(service, message_body: dict):
    """
    Envía el correo usando users.messages.send con userId='me'.
    """
    return (
        service.users()
        .messages()
        .send(userId="me", body=message_body)
        .execute()
    )


def send_email_alert(
    to_emails: Iterable[str] | str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
):
    """
    Envía un correo de alerta simple.
    El sender_email sale automáticamente del token autenticado.
    """
    service = get_gmail_service()

    sender_email = os.getenv("GMAIL_SENDER_EMAIL")
    if not sender_email:
        raise ValueError("Falta GMAIL_SENDER_EMAIL en el entorno.")
    

    sender_name = os.getenv("GMAIL_SENDER_NAME", "Prospect Alerts").strip() or None

    message_body = create_message(
        sender_email=sender_email,
        sender_name=sender_name,
        to_emails=to_emails,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

    result = send_message(service, message_body)
    return result


def send_bot_alert(
    severity: str,
    event: str,
    details: str,
    metadata: Optional[dict] = None,
):
    """
    Helper orientado a alertas del bot.
    """
    app_name = os.getenv("APP_NAME", "Bot").strip()
    app_env = os.getenv("APP_ENV", "local").strip()
    to_email = os.getenv("GMAIL_ALERT_TO", "").strip()

    if not to_email:
        raise ValueError("Falta GMAIL_ALERT_TO en el entorno.")

    severity = severity.upper().strip()
    subject = f"[{app_name}][{app_env.upper()}][{severity}] {event}"

    meta_lines = []
    meta_html = ""

    if metadata:
        for key, value in metadata.items():
            meta_lines.append(f"{key}: {value}")

        meta_html_rows = "".join(
            f"<li><strong>{key}:</strong> {value}</li>"
            for key, value in metadata.items()
        )
        meta_html = f"<ul>{meta_html_rows}</ul>"

    text_body = (
        f"Alerta del bot\n\n"
        f"Aplicación: {app_name}\n"
        f"Entorno: {app_env}\n"
        f"Severidad: {severity}\n"
        f"Evento: {event}\n\n"
        f"Detalle:\n{details}\n"
    )

    if meta_lines:
        text_body += "\nMetadata:\n" + "\n".join(meta_lines)

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.5;">
        <h2>Alerta del bot</h2>
        <p><strong>Aplicación:</strong> {app_name}</p>
        <p><strong>Entorno:</strong> {app_env}</p>
        <p><strong>Severidad:</strong> {severity}</p>
        <p><strong>Evento:</strong> {event}</p>
        <p><strong>Detalle:</strong><br>{details.replace(chr(10), "<br>")}</p>
        {meta_html}
      </body>
    </html>
    """

    return send_email_alert(
        to_emails=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


if __name__ == "__main__":
    try:
        response = send_bot_alert(
            severity="CRITICAL",
            event="Proxy failure",
            details="El bot detectó 10 errores consecutivos al usar el proxy principal.",
            metadata={
                "bot_id": "crawler_01",
                "proxy": "181.xxx.xxx.xxx",
                "attempts": 10,
            },
        )
        print("Correo enviado correctamente:")
        print(response)
    except HttpError as e:
        print(f"Error HTTP de Gmail API: {e}")
    except Exception as e:
        print(f"Error general: {e}")