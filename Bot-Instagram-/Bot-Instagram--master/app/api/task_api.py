import json
import os
import socket

import requests
from dotenv import load_dotenv

load_dotenv()


def _normalize_api_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        value = "http://localhost:8000/api/"
    value = value.rstrip("/")
    if not value.endswith("/api"):
        value += "/api"
    return value.rstrip("/") + "/"


class TaskAPI:
    def __init__(self):
        env_url = (
            os.getenv("TASK_API_URL")
            or os.getenv("BACKEND_API_URL")
            or os.getenv("API_BASE_URL")
            or os.getenv("BACKEND_BASE_URL")
            or os.getenv("API_URL")
            or "http://localhost:8000/api/"
        )
        self.url = _normalize_api_url(env_url)
        self.bot_executor = (
            os.getenv("BOT_EXECUTOR_NAME")
            or os.getenv("BOT_EXECUTOR")
            or os.getenv("BOT_NAME")
            or f"Bot_Instagram_{socket.gethostname()}"
        ).strip()
        self.headers = {"accept": "application/json", "Content-Type": "application/json"}
        self.claim_headers = dict(self.headers)
        token = os.getenv("TASK_API_TOKEN", "").strip()
        if token:
            self.claim_headers["Authorization"] = f"Bearer {token}"
        print(f"[TaskAPI] Conectado a: {self.url} | executor={self.bot_executor}")

    def claim_next_task(self, bot_executor: str | None = None):
        executor = (bot_executor or self.bot_executor or "").strip()
        if not executor:
            return False, None
        try:
            response = requests.post(
                self.url + "orchestrator/instagram/tasks/claim/",
                headers=self.claim_headers,
                json={"bot_executor": executor},
                timeout=15,
            )
            if response.status_code == 200:
                payload = response.json()
                return True, payload.get("task")
            if response.status_code not in (404, 405):
                print(f"[TaskAPI] Claim rejected | status={response.status_code}")
                return True, None
            print(
                "[TaskAPI] Claim endpoint unavailable | "
                f"status={response.status_code} | body={response.text}"
            )
        except Exception as exc:
            print(f"[TaskAPI] Claim endpoint unavailable: {exc}")
            return True, None
        return False, None

    def get_pending_bots(self):
        claim_available, claimed = self.claim_next_task()
        if claim_available:
            return True, [claimed] if claimed else []

        # Compatibility fallback for a backend that does not expose the claim endpoint.
        try:
            response = requests.get(self.url + "pending_bots/", headers=self.headers, timeout=10)
            if response.status_code == 200:
                return True, response.json()
            print(
                "[TaskAPI] Error consultando pending_bots | "
                f"status={response.status_code} | body={response.text}"
            )
            return False, None
        except Exception as exc:
            print(f"Error inesperado al consultar bots pendientes: {exc}")
            return False, None

    def update_task(self, id, bot_executor, status_process, comment, end_date=None):
        data = {
            "bot_executor": bot_executor,
            "status_process": status_process,
            "comment": comment,
            "end_date": end_date,
        }
        try:
            response = requests.put(
                self.url + f"task_bots/{id}/",
                headers=self.headers,
                json=data,
                timeout=30,
            )
            if response.status_code == 200:
                return True, response.json()
            print(
                "[TaskAPI] Error actualizando task_bot | "
                f"id={id} | status={response.status_code} | body={response.text}"
            )
            try:
                return False, response.json()
            except Exception:
                return False, response.text
        except Exception as exc:
            print(f"[TaskAPI] Error inesperado actualizando task_bot {id}: {exc}")
            return False, str(exc)

    def save_img_url(self, id, img_url):
        url = self.url + f"pending_bots/{id}/"
        params = {"custom_task": {"links_image": img_url, "type": "muro"}}
        try:
            return requests.patch(url, data=json.dumps(params), headers=self.headers, timeout=30)
        except Exception as exc:
            print(f"[TaskAPI] Error inesperado guardando imagen en pending_bot {id}: {exc}")
            raise
