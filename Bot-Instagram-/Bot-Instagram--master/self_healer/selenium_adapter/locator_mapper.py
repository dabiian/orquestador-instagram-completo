"""Map Selenium locators to the internal locator candidate format."""

from __future__ import annotations

import re
from typing import Tuple

from selenium.webdriver.common.by import By

from ..core.exceptions import InvalidLocatorCandidate
from ..core.models import LocatorCandidate


# HTML tag names are intentionally conservative here. Selenium's
# By.TAG_NAME expects an actual element name, not a CSS expression.
_TAG_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9:_-]*$")


def _require_value(value: str) -> str:
    """Normalize and validate a Selenium locator value."""
    if value is None:
        raise InvalidLocatorCandidate("Locator value cannot be None.")

    value = str(value)

    if not value.strip():
        raise InvalidLocatorCandidate("Locator value cannot be empty.")

    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise InvalidLocatorCandidate(
            "Locator value contains unsupported control characters."
        )

    return value


def _css_string(value: str) -> str:
    """
    Escape a value for use as a double-quoted CSS string.

    This is used for attribute selectors such as:
        [id="..."]
        [name="..."]
        [class~="..."]
    """
    value = _require_value(value)

    escaped: list[str] = []

    for char in value:
        if char == "\\":
            escaped.append("\\\\")
        elif char == '"':
            escaped.append('\\"')
        elif char == "\n":
            escaped.append("\\A ")
        elif char == "\r":
            escaped.append("\\D ")
        elif char == "\f":
            escaped.append("\\C ")
        else:
            escaped.append(char)

    return '"' + "".join(escaped) + '"'


def _xpath_literal(value: str) -> str:
    """
    Return a valid XPath string literal for an arbitrary value.

    XPath 1.0 does not provide an escaping mechanism inside quoted
    string literals, so values containing both quote types must be
    represented with concat().
    """
    value = _require_value(value)

    if "'" not in value:
        return f"'{value}'"

    if '"' not in value:
        return f'"{value}"'

    # Both quote types occur in the value.
    #
    # Split on single quotes. Every resulting segment can safely use
    # double quotes. The single quote itself is inserted as a literal
    # XPath string containing one single quote.
    parts = value.split("'")
    expressions: list[str] = []

    for index, part in enumerate(parts):
        if part:
            expressions.append(f"'{part}'")

        if index < len(parts) - 1:
            expressions.append('"\'"')

    if not expressions:
        return '""'

    return "concat(" + ", ".join(expressions) + ")"


def _normalize_strategy(strategy: str) -> str:
    """Normalize internal/Selenium locator strategy names."""
    normalized = str(strategy or "").strip().lower()

    aliases = {
        "css": "css",
        "css selector": "css",
        "css_selector": "css",
        "xpath": "xpath",
    }

    try:
        return aliases[normalized]
    except KeyError as exc:
        raise InvalidLocatorCandidate(
            f"Unsupported internal locator strategy: {strategy}"
        ) from exc


def _validate_tag_name(value: str) -> str:
    """Validate a Selenium By.TAG_NAME value."""
    value = _require_value(value).strip()

    if not _TAG_NAME_RE.fullmatch(value):
        raise InvalidLocatorCandidate(
            f"Invalid Selenium tag name: {value!r}"
        )

    return value


def map_by_to_candidate(by: str, value: str) -> LocatorCandidate:
    """
    Convert a Selenium By strategy into the internal locator format.

    Selenium supports several locator strategies while Self-Healer
    internally works with only CSS and XPath. Strategies that do not
    have a direct CSS equivalent are translated to XPath while
    preserving their Selenium semantics.
    """
    if by is None:
        raise InvalidLocatorCandidate("Selenium locator strategy cannot be None.")

    by = str(by).strip()
    value = _require_value(value)

    if by == By.ID:
        return LocatorCandidate(
            strategy="css",
            value=f"[id={_css_string(value)}]",
            name="id",
        )

    if by == By.NAME:
        return LocatorCandidate(
            strategy="css",
            value=f"[name={_css_string(value)}]",
            name="name",
        )

    if by == By.CSS_SELECTOR:
        return LocatorCandidate(
            strategy="css",
            value=value,
            name="css",
        )

    if by == By.XPATH:
        return LocatorCandidate(
            strategy="xpath",
            value=value,
            name="xpath",
        )

    if by == By.CLASS_NAME:
        # Selenium's By.CLASS_NAME expects one class token.
        if any(char.isspace() for char in value):
            raise InvalidLocatorCandidate(
                "By.CLASS_NAME requires a single class name."
            )

        return LocatorCandidate(
            strategy="css",
            value=f"[class~={_css_string(value)}]",
            name="class",
        )

    if by == By.TAG_NAME:
        tag_name = _validate_tag_name(value)

        return LocatorCandidate(
            strategy="css",
            value=tag_name,
            name="tag",
        )

    if by == By.LINK_TEXT:
        return LocatorCandidate(
            strategy="xpath",
            value=(
                f"//a[normalize-space(.)={_xpath_literal(value)}]"
            ),
            name="link_text",
        )

    if by == By.PARTIAL_LINK_TEXT:
        return LocatorCandidate(
            strategy="xpath",
            value=(
                "//a[contains("
                f"normalize-space(.), {_xpath_literal(value)}"
                ")]"
            ),
            name="partial_link_text",
        )

    raise InvalidLocatorCandidate(
        f"Unsupported Selenium locator strategy: {by}"
    )


def candidate_to_by(candidate: LocatorCandidate) -> Tuple[str, str]:
    """
    Convert an internal LocatorCandidate into Selenium's By tuple.

    Returns:
        (selenium_strategy, locator_value)
    """
    if candidate is None:
        raise InvalidLocatorCandidate("Locator candidate cannot be None.")

    strategy = _normalize_strategy(candidate.strategy)
    value = _require_value(candidate.value)

    if strategy == "css":
        return By.CSS_SELECTOR, value

    if strategy == "xpath":
        return By.XPATH, value

    # Kept for defensive completeness even though _normalize_strategy()
    # already limits the possible values.
    raise InvalidLocatorCandidate(
        f"Unsupported internal locator strategy: {candidate.strategy}"
    )
