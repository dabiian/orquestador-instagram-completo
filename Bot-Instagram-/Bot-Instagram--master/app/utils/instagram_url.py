import re

def _normalize_instagram_href(href: str) -> str:
    """Canonicalize Instagram profile/post/reel URLs for deduplication."""
    from urllib.parse import urlsplit
    href = str(href or "").strip()
    if not href:
        return ""
    # Never normalize browser error pages, javascript/data URLs or other
    # non-Instagram navigation artifacts into fake Instagram URLs.
    lowered = href.lower()
    if (lowered.startswith(("chrome-error://", "about:", "javascript:", "data:"))
            or "chrome-error" in lowered):
        return ""
    if href.startswith("/"):
        href = f"https://www.instagram.com{href}"
    if not href.startswith(("http://", "https://")):
        href = "https://www.instagram.com/" + href.lstrip("/")
    try:
        parsed = urlsplit(href)
        host = (parsed.netloc or "www.instagram.com").lower()
        if not (host == "instagram.com" or host.endswith(".instagram.com")):
            return ""
        host = "www.instagram.com"
        path = re.sub(r"/+", "/", parsed.path or "/").strip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[-2].lower() in {"p", "reel", "reels", "tv"}:
            kind = parts[-2].lower()
            if kind == "reels":
                kind = "reel"
            return f"https://{host}/{kind}/{parts[-1]}/"
        if len(parts) >= 3 and parts[-2].lower() not in {"p", "reel", "reels", "tv"} and parts[-3].lower() in {"p", "reel", "reels", "tv"}:
            kind = parts[-3].lower()
            if kind == "reels":
                kind = "reel"
            return f"https://{host}/{kind}/{parts[-2]}/"
        return f"https://{host}/{path}/" if path else f"https://{host}/"
    except Exception:
        return href.split("?", 1)[0].split("#", 1)[0].rstrip("/") + "/"


def _extract_username_from_url(url: str) -> str:
    """
    Extrae únicamente el username de una URL de perfil de Instagram.

    Ejemplos:
        https://www.instagram.com/kashkeeshlaw/
            -> kashkeeshlaw

        https://www.instagram.com/p/CwvpYJLviu2/
            -> ""

        https://www.instagram.com/reel/ABC123/
            -> ""

        https://www.instagram.com/explore/tags/chicagorealtor/
            -> ""
    """
    try:
        url = str(url or "").strip()

        if not url:
            return ""

        normalized = _normalize_instagram_href(url)

        parts = [
            part.strip()
            for part in normalized.split("/")
            if part.strip()
        ]

        # https://www.instagram.com/usuario/
        if len(parts) != 3:
            return ""

        if parts[0].lower() not in {"https:", "http:"}:
            return ""

        if parts[1].lower() != "www.instagram.com":
            return ""

        username = parts[2].strip().lower()

        if not username:
            return ""

        invalid_usernames = {
            "p",
            "reel",
            "reels",
            "tv",
            "explore",
            "stories",
            "accounts",
            "direct",
            "about",
        }

        if username in invalid_usernames:
            return ""

        return username

    except Exception:
        return ""


def _normalize_instagram_href_v2(href: str) -> str:
    return _normalize_instagram_href(href)



def _is_valid_profile(href: str) -> bool:
    if not href:
        return False

    invalid_parts = [
        "/followers/",
        "/following/",
        "/explore/",
        "/reels/",
        "/reel/",
        "/p/",
        "/stories/",
        "/accounts/",
    ]

    for part in invalid_parts:
        if part in href:
            return False

    username = _extract_username_from_url(href)
    return bool(username)