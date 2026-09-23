import base64
import requests


def _download_image_as_data_url(url: str):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.instagram.com/",
        }

        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()

        content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
        if not content_type.startswith("image/"):
            return False, None

        b64 = base64.b64encode(resp.content).decode("utf-8")
        data_url = f"data:{content_type};base64,{b64}"
        return True, data_url

    except Exception:
        return False, None