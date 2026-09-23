"""Deterministic guards for Instagram hashtag search navigation.

These helpers are intentionally dependency-free so the safety invariant can be
unit-tested without a live browser: a requested hashtag may only resolve to the
exact Instagram /explore/tags/<slug>/ destination.
"""

from urllib.parse import unquote, urlparse


HASHTAG_RESULT_URL_PART = "/explore/tags/"


def normalize_hashtag_slug(value: str) -> str:
    value = unquote(str(value or "").strip())
    if value.startswith("#"):
        value = value[1:]
    return value.strip().strip("/").lower()


def extract_hashtag_slug_from_href(href: str) -> str:
    try:
        raw = unquote(str(href or "").strip())
        parsed = urlparse(raw)
        path = parsed.path or raw.split("?", 1)[0].split("#", 1)[0]
        if HASHTAG_RESULT_URL_PART not in path:
            return ""
        slug = path.split(HASHTAG_RESULT_URL_PART, 1)[1].split("/", 1)[0]
        return normalize_hashtag_slug(slug)
    except Exception:
        return ""


def hashtag_href_matches_slug(href: str, requested_slug: str) -> bool:
    actual = extract_hashtag_slug_from_href(href)
    expected = normalize_hashtag_slug(requested_slug)
    return bool(actual and expected and actual == expected)


def canonical_hashtag_href(href: str) -> str:
    slug = extract_hashtag_slug_from_href(href)
    if not slug:
        return ""
    return f"https://www.instagram.com/explore/tags/{slug}/"
