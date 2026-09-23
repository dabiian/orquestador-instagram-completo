import json
import mimetypes
import uuid
import requests
import os
import base64
from dotenv import load_dotenv

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


class AccountAPI:
    """
    Gestión de cuenta: cookies, mensajes guardados, descarga de imágenes.
    """

    def __init__(self):
        env_url = (
            os.getenv("ACCOUNT_API_URL")
            or os.getenv("BACKEND_API_URL")
            or os.getenv("TASK_API_URL")
            or os.getenv("API_BASE_URL")
            or os.getenv("BACKEND_BASE_URL")
            or os.getenv("API_URL")
            or "http://localhost:8000/api/"
        )

        self.url = _normalize_api_url(env_url)

        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        print("[AccountAPI] Conectado a:", self.url)

    def download_image(self, url, filename):
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        with open(filename, "wb") as file:
            file.write(response.content)

        absolute_path = os.path.abspath(filename)
        print(f"Imagen descargada y guardada como {absolute_path}")
        return absolute_path

    def update_cookie(self, id_user, cookies):
        url = self.url + f"social_media_accounts/{id_user}/update_cookie/"

        try:
            response = requests.patch(
                url,
                headers=self.headers,
                json=cookies,
                timeout=30,
            )

            if response.status_code == 200:
                print("Cookie actualizada con éxito")
                return True, response.json()

            print(
                "[AccountAPI] Error al actualizar la cookie | "
                f"status={response.status_code} | body={response.text}"
            )

            try:
                return False, response.json()
            except Exception:
                return False, response.text

        except Exception as e:
            print(f"[AccountAPI] Error inesperado actualizando cookie: {e}")
            return False, str(e)

    def get_comments(self, account_id, category: str | None = None):
        url = self.url + "account_messages/"

        params = (
            {"account_id": account_id}
            if not category
            else {"account_id": account_id, "category": category}
        )

        try:
            response = requests.get(
                url,
                headers={"accept": "application/json"},
                params=params,
                timeout=30,
            )

            return response

        except Exception as e:
            print(f"[AccountAPI] Error inesperado consultando comentarios: {e}")
            raise

    def save_new_comment(self, account_id, message_text, category, metadata):
        url = self.url + "account_messages/"

        params = {
            "account_id": account_id,
            "message_text": message_text,
            "category": category,
            "status": "active",
            "metadata": metadata,
        }

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=params,
                timeout=30,
            )

            return response

        except Exception as e:
            print(f"[AccountAPI] Error inesperado guardando comentario: {e}")
            raise