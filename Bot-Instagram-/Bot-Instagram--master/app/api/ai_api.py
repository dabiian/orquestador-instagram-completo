import json
import mimetypes
import uuid
import requests
import base64
from dotenv import load_dotenv
import os
from urllib.parse import urlparse
from app.utils.story_image_composer import compose_story_image

load_dotenv()

import random
import re


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


class AIAPI:
    """
    API de inteligencia artificial que encapsula la lógica de generación de respuestas.
    Consume: `IBrowser`, `ILoginService` (opcional).
    """

    def __init__(self):
        env_url = (
            os.getenv("AI_API_URL")
            or os.getenv("BACKEND_API_URL")
            or os.getenv("TASK_API_URL")
            or os.getenv("API_BASE_URL")
            or os.getenv("BACKEND_BASE_URL")
            or os.getenv("API_URL")
            or "http://localhost:8000/api/"
        )

        self.url = _normalize_api_url(env_url)
        self.headers = {"accept": "application/json"}

        print("[AIAPI] Conectado a:", self.url)

    def get_bot_ia(self, bot_personality_id, user_prompt):
        params = {"bot_personality_id": bot_personality_id, "user_prompt": user_prompt}
        try:
            response = requests.get(
                self.url + "openai/",
                headers=self.headers,
                params=params,
                timeout=100,
            )
            response.raise_for_status()
            return True, response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"Error HTTP: {http_err}")
            return False, None
        except requests.exceptions.ConnectionError as conn_err:
            print(f"Error de conexión get_bot_ia: {conn_err}")
            return False, None
        except requests.exceptions.Timeout as timeout_err:
            print(f"Error de tiempo de espera: {timeout_err}")
            return False, None
        except requests.exceptions.RequestException as req_err:
            print(f"Error en la solicitud: {req_err}")
            return False, None

    def get_bot_ia_long_prompt(self, bot_personality_id, user_prompt):
        """
        Método seguro para prompts largos.
        Usa POST primero para evitar URL gigante.
        Si el backend no soporta POST, cae al GET viejo.
        Así no rompe tareas anteriores.
        """
        url = self.url + "openai/"

        post_headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = {
            "bot_personality_id": bot_personality_id,
            "user_prompt": user_prompt,
        }

        last_error = None

        for attempt in range(1, 4):
            try:
                response = requests.post(
                    url,
                    headers=post_headers,
                    json=payload,
                    timeout=180,
                )

                response.raise_for_status()
                return True, response.json()

            except requests.exceptions.HTTPError as http_err:
                last_error = http_err
                status_code = getattr(http_err.response, "status_code", None)

                response_body = (getattr(http_err.response, "text", "") or "").strip()
                print(
                    f"Error HTTP get_bot_ia_long_prompt POST intento {attempt}/3: "
                    f"{http_err} | status={status_code} | body={response_body[:1000]!r}"
                )

                # Algunos despliegues antiguos/mixtos exponen el contrato GET
                # y responden 5xx al POST. Recuperamos con el contrato histórico
                # para no convertir un problema de método en un descarte de
                # prospectos. Para 5xx se intenta una sola vez por intento; si
                # también falla, se mantiene el error real para el siguiente.
                if status_code in (404, 405, 500, 502, 503, 504):
                    try:
                        params = {
                            "bot_personality_id": bot_personality_id,
                            "user_prompt": user_prompt,
                        }

                        fallback_response = requests.get(
                            url,
                            headers=self.headers,
                            params=params,
                            timeout=120,
                        )

                        fallback_response.raise_for_status()
                        return True, fallback_response.json()

                    except Exception as fallback_err:
                        last_error = fallback_err
                        fallback_body = (getattr(locals().get("fallback_response", None), "text", "") or "").strip()
                        print(
                            f"Fallback GET get_bot_ia_long_prompt falló intento {attempt}/3: "
                            f"{fallback_err} | body={fallback_body[:1000]!r}"
                        )

            except requests.exceptions.ConnectionError as conn_err:
                last_error = conn_err
                print(
                    f"Error de conexión get_bot_ia_long_prompt intento {attempt}/3: "
                    f"{conn_err}"
                )

            except requests.exceptions.Timeout as timeout_err:
                last_error = timeout_err
                print(
                    f"Timeout get_bot_ia_long_prompt intento {attempt}/3: "
                    f"{timeout_err}"
                )

            except requests.exceptions.RequestException as req_err:
                last_error = req_err
                print(
                    f"Error en get_bot_ia_long_prompt intento {attempt}/3: "
                    f"{req_err}"
                )

        print(f"get_bot_ia_long_prompt falló después de 3 intentos: {last_error}")
        return False, None

    def download_image_edited(
        self,
        image_b64,
        filename,
        account_name="not_provided",
        asset_type="histories",
    ):
        """
        Guarda la imagen base64 en:
        app/utilities/images/{asset_type}/generated/{account_name}/{filename}
        """
        if not image_b64:
            raise ValueError("image_b64 vacío")

        if image_b64.startswith("data:") and "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        data = base64.b64decode(image_b64)

        base_dir = self._build_asset_dir(
            account_name=account_name,
            asset_type=asset_type,
            bucket="generated",
        )

        full_path = os.path.join(base_dir, filename)

        with open(full_path, "wb") as f:
            f.write(data)

        abs_path = os.path.abspath(full_path)
        print(f"Imagen descargada y guardada como {abs_path}")
        return abs_path

    def get_img_edited(self, img_path, user_prompt, username, size_image="auto"):
        url = self.url + "openai/image/edit/"
        mime = mimetypes.guess_type(img_path)[0] or "application/octet-stream"

        with open(img_path, "rb") as f:
            files = {"image": (os.path.basename(img_path), f, mime)}
            data = {
                "user_prompt": user_prompt,
                "size_image": size_image,
            }
            try:
                r = requests.post(url, files=files, data=data, timeout=180)
            except Exception as e:
                print("error en la peticion: " + str(e))
                return None

            r.raise_for_status()

        payload = r.json()
        if payload.get("message") != "ok" or not payload.get("image_b64"):
            raise RuntimeError(f"Respuesta inválida: {payload}")

        img_edited_path = self.download_image_edited(
            payload["image_b64"],
            f"{uuid.uuid4().hex}.png",
            username,
        )
        return img_edited_path

    def analize_image(self, prompt, url=None, image_base64=None):
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        data = {"prompt": prompt}

        if image_base64:
            data["image_base64"] = image_base64
        elif url:
            data["url"] = url
        else:
            print("Error analize_image: no se recibió ni url ni image_base64")
            return False, {"error": "no_image_input"}

        try:
            response = requests.post(
                self.url + "openai/image/anality/",
                headers=headers,
                json=data,
                timeout=120,
            )

            print(f"[analize_image] status_code={response.status_code}")

            try:
                data_ai = response.json()
            except Exception:
                data_ai = {"raw_text": response.text}

            print(f"[analize_image] body={data_ai}")

            if response.status_code != 200:
                return False, data_ai

            if not isinstance(data_ai, dict):
                return False, {"error": "invalid_backend_payload", "payload": data_ai}

            status_ai = data_ai.get("status")
            response_ai = data_ai.get("response")
            error_ai = data_ai.get("error")

            print(f"[analize_image] status={status_ai} | response={response_ai} | error={error_ai}")

            if status_ai is True and response_ai:
                return True, str(response_ai).strip()

            return False, data_ai

        except Exception as e:
            print(f"Se produjo un error en analize_image: {e}")
            return False, {"error": str(e)}

    def generate_instagram_story_asset(
        self,
        bot_personality_id,
        username,
        campaign_name="",
        business_name="",
        category="",
        location="",
        extra_context="",
        forced_style=None,
        size_image="1024x1792",
        account_kind=None,
    ):
        resolved_account_kind = account_kind or "business"

        return self.get_story_asset(
            bot_personality_id=bot_personality_id,
            username=username,
            account_kind=resolved_account_kind,
            campaign_name=campaign_name,
            business_name=business_name,
            category=category,
            location=location,
            extra_context=extra_context,
            forced_style=forced_style,
            size_image=size_image,
            quality_image="medium",
        )

    def get_story_asset(
        self,
        bot_personality_id,
        username,
        account_kind="business",
        campaign_name="",
        business_name="",
        category="",
        location="",
        extra_context="",
        forced_style=None,
        size_image="1024x1792",
        quality_image="medium",
    ):
        url = self.url + "openai/story-asset/"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = {
            "bot_personality_id": bot_personality_id,
            "account_kind": account_kind,
            "campaign_name": campaign_name,
            "business_name": business_name,
            "category": category,
            "location": location,
            "extra_context": extra_context,
            "forced_style": forced_style,
            "size_image": size_image,
            "quality_image": quality_image,
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=180)
            response.raise_for_status()

            data = response.json()
            if not data.get("status"):
                return False, data

            image_b64 = data.get("image_b64")
            if not image_b64:
                return False, {"error": "image_b64_missing", "payload": data}

            final_image_path = self.download_image_edited(
                image_b64=image_b64,
                filename=f"{uuid.uuid4().hex}.png",
                account_name=username,
                asset_type="histories",
            )

            return True, {
                "image_path": final_image_path,
                "style": data.get("style", ""),
                "headline": data.get("headline", ""),
                "brief": data.get("brief", {}),
                "raw": data,
            }

        except requests.exceptions.HTTPError as http_err:
            print(f"Error HTTP get_story_asset: {http_err}")
            try:
                return False, response.json()
            except Exception:
                return False, {"error": str(http_err)}

        except requests.exceptions.ConnectionError as conn_err:
            print(f"Error de conexión get_story_asset: {conn_err}")
            return False, {"error": str(conn_err)}

        except requests.exceptions.Timeout as timeout_err:
            print(f"Timeout get_story_asset: {timeout_err}")
            return False, {"error": str(timeout_err)}

        except requests.exceptions.RequestException as req_err:
            print(f"Error en get_story_asset: {req_err}")
            return False, {"error": str(req_err)}

    def generate_instagram_post_asset(
        self,
        bot_personality_id,
        social_media_account_id,
        username,
        campaign_name="",
        business_name="",
        category="",
        location="",
        extra_context="",
        post_mode=None,
        max_images=2,
        image_text_mode="overlay",
        size_image="1024x1024",
        account_kind=None,
        memory_asset_type=None,
    ):
        resolved_account_kind = account_kind or "business"

        return self.get_post_asset(
            bot_personality_id=bot_personality_id,
            social_media_account_id=social_media_account_id,
            username=username,
            account_kind=resolved_account_kind,
            campaign_name=campaign_name,
            business_name=business_name,
            category=category,
            location=location,
            extra_context=extra_context,
            post_mode=post_mode,
            max_images=max_images,
            image_text_mode=image_text_mode,
            size_image=size_image,
            quality_image="medium",
            memory_asset_type=memory_asset_type,
        )

    def get_post_asset(
        self,
        bot_personality_id,
        social_media_account_id,
        username,
        account_kind="business",
        campaign_name="",
        business_name="",
        category="",
        location="",
        extra_context="",
        post_mode=None,
        max_images=2,
        image_text_mode="overlay",
        size_image="1024x1024",
        quality_image="medium",
        memory_asset_type=None,
    ):
        url = self.url + "openai/post-asset/"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = {
            "bot_personality_id": bot_personality_id,
            "social_media_account_id": social_media_account_id,
            "account_kind": account_kind,
            "campaign_name": campaign_name,
            "business_name": business_name,
            "category": category,
            "location": location,
            "extra_context": extra_context,
            "post_mode": post_mode,
            "max_images": max_images,
            "image_text_mode": image_text_mode,
            "size_image": size_image,
            "quality_image": quality_image,
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=240)
            response.raise_for_status()

            data = response.json()
            if not data.get("status"):
                return False, data

            images = data.get("images") or []
            if not images:
                return False, {"error": "images_missing", "payload": data}

            saved_images = []
            for index, img in enumerate(images, start=1):
                image_b64 = img.get("image_b64")
                if not image_b64:
                    continue

                image_path = self.download_image_edited(
                    image_b64=image_b64,
                    filename=f"{uuid.uuid4().hex}_{index}.png",
                    account_name=username,
                    asset_type="posts",
                )

                saved_images.append(image_path)

            if not saved_images:
                return False, {"error": "no_images_saved", "payload": data}

            return True, {
                "images": saved_images,
                "caption_with_hashtags": data.get("caption_with_hashtags", "").strip(),
                "headline": data.get("headline", "").strip(),
            }

        except requests.exceptions.HTTPError as http_err:
            print(f"Error HTTP get_post_asset: {http_err}")
            try:
                return False, response.json()
            except Exception:
                return False, {"error": str(http_err)}

        except requests.exceptions.ConnectionError as conn_err:
            print(f"Error de conexión get_post_asset: {conn_err}")
            return False, {"error": str(conn_err)}

        except requests.exceptions.Timeout as timeout_err:
            print(f"Timeout get_post_asset: {timeout_err}")
            return False, {"error": str(timeout_err)}

        except requests.exceptions.RequestException as req_err:
            print(f"Error en get_post_asset: {req_err}")
            return False, {"error": str(req_err)}

    def save_content_memory(
        self,
        social_media_account_id,
        asset_type,
        caption_text="",
        overlay_phrase="",
    ):
        url = self.url + "content-memory/"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = {
            "social_media_account_id": social_media_account_id,
            "asset_type": asset_type,
            "caption_text": caption_text,
            "overlay_phrase": overlay_phrase,
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return True, response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error guardando content memory: {e}")
            try:
                return False, response.json()
            except Exception:
                return False, {"error": str(e)}

    def analyze_followback_image(self, url=None, image_base64=None):
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        data = {}

        if image_base64:
            data["image_base64"] = image_base64
        elif url:
            data["url"] = url
        else:
            print("Error analyze_followback_image: no se recibió ni url ni image_base64")
            return False, {"error": "no_image_input"}

        try:
            response = requests.post(
                self.url + "openai/image/followback-classify/",
                headers=headers,
                json=data,
                timeout=120,
            )

            print(f"[analyze_followback_image] status_code={response.status_code}")

            try:
                data_ai = response.json()
            except Exception:
                data_ai = {"raw_text": response.text}

            print(f"[analyze_followback_image] body={data_ai}")

            if response.status_code != 200:
                return False, data_ai

            if not isinstance(data_ai, dict):
                return False, {"error": "invalid_backend_payload", "payload": data_ai}

            status_ai = data_ai.get("status")
            result_ai = data_ai.get("result")
            error_ai = data_ai.get("error")

            print(
                f"[analyze_followback_image] status={status_ai} | "
                f"result={result_ai} | error={error_ai}"
            )

            if status_ai is True and isinstance(result_ai, dict):
                return True, result_ai

            return False, data_ai

        except Exception as e:
            print(f"Se produjo un error en analyze_followback_image: {e}")
            return False, {"error": str(e)}

    def _build_asset_dir(self, account_name="not_provided", asset_type="histories", bucket="generated"):
        asset_type = (asset_type or "histories").strip().lower()
        if asset_type not in {"histories", "posts", "tagged"}:
            asset_type = "histories"

        bucket = (bucket or "generated").strip().lower()
        if bucket not in {"generated", "downloaded"}:
            bucket = "generated"

        base_dir = os.path.join(
            "app",
            "utilities",
            "images",
            asset_type,
            bucket,
            account_name,
        )

        os.makedirs(base_dir, exist_ok=True)
        return base_dir