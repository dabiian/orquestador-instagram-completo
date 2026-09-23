"""Candidate validation helpers for Web/Selenium locators.

The validator performs local syntactic and safety checks.

It does NOT determine whether a locator actually exists in the
current browser DOM.

Actual locator existence must be verified against Selenium.
"""

from __future__ import annotations

import re

from .exceptions import InvalidLocatorCandidate
from .models import LocatorCandidate
import logging

logger = logging.getLogger(__name__)

# ================================================================
# SUPPORTED STRATEGIES
# ================================================================

SUPPORTED_STRATEGIES = {
    "css",
    "xpath",
}


# ================================================================
# LIMITS
# ================================================================

MAX_LOCATOR_LENGTH = 2048


# ================================================================
# UNSAFE / NON-LOCATOR PATTERNS
# ================================================================

# Absolute XPath examples:
#
# /html/body/div[1]/div[2]
# /html/body/main
#
# Relative XPath is allowed:
#
# //button
# .//button
# ./div
#
_ABSOLUTE_XPATH_RE = re.compile(
    r"^/(?!/)"
)


# JavaScript should never be accepted as a locator.
#
# Examples:
#
# javascript:alert(1)
# return document.querySelector(...)
# function(...)
# document.querySelector(...)
# window.location
# () => ...
#
_JS_RE = re.compile(
    r"""
    (?:
        \bjavascript\s*:
        |
        \breturn\s+
        |
        \bfunction\s*
        \(
        |
        =>
        |
        \bdocument\s*\.
        |
        \bwindow\s*\.
        |
        \beval\s*\(
        |
        \bsetTimeout\s*\(
        |
        \bsetInterval\s*\(
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


# Selenium / automation code accidentally returned as a locator.
#
# Examples:
#
# driver.find_element(...)
# self.driver.find_element(...)
# By.XPATH
# By.CSS_SELECTOR
#
_AUTOMATION_CODE_RE = re.compile(
    r"""
    (?:
        \bdriver\s*\.\s*find_element
        |
        \bfind_element\s*\(
        |
        \bfind_elements\s*\(
        |
        \bBy\s*\.\s*
            (?:
                XPATH
                |
                CSS_SELECTOR
                |
                ID
                |
                NAME
                |
                CLASS_NAME
                |
                TAG_NAME
                |
                LINK_TEXT
                |
                PARTIAL_LINK_TEXT
            )
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


# Common Python/JavaScript code markers.
_CODE_RE = re.compile(
    r"""
    (?:
        ^\s*(?:def|class|import|from)\s+
        |
        ^\s*(?:const|let|var)\s+
        |
        \basync\s+function\b
        |
        \bawait\s+
        |
        \bconsole\s*\.
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ================================================================
# CSS VALIDATION HELPERS
# ================================================================


def _validate_css_syntax(
    value: str,
) -> None:
    """Perform lightweight CSS selector validation.

    This intentionally does not implement the complete CSS grammar.

    Browser/Selenium remains the final authority.

    The goal is to reject obviously malformed or dangerous values
    while allowing modern CSS selectors.
    """

    # ------------------------------------------------------------
    # Balanced brackets
    # ------------------------------------------------------------

    square_depth = 0
    parentheses_depth = 0

    quote: str | None = None
    escaped = False

    for char in value:

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if quote:

            if char == quote:
                quote = None

            continue

        if char in {
            "'",
            '"',
        }:

            quote = char
            continue

        if char == "[":
            square_depth += 1

        elif char == "]":

            square_depth -= 1

            if square_depth < 0:
                raise InvalidLocatorCandidate(
                    "CSS selector contains unmatched ']'."
                )

        elif char == "(":
            parentheses_depth += 1

        elif char == ")":

            parentheses_depth -= 1

            if parentheses_depth < 0:
                raise InvalidLocatorCandidate(
                    "CSS selector contains unmatched ')'."
                )

    if quote:
        raise InvalidLocatorCandidate(
            "CSS selector contains an unterminated quote."
        )

    if square_depth != 0:
        raise InvalidLocatorCandidate(
            "CSS selector contains unbalanced brackets."
        )

    if parentheses_depth != 0:
        raise InvalidLocatorCandidate(
            "CSS selector contains unbalanced parentheses."
        )


# ================================================================
# XPATH VALIDATION HELPERS
# ================================================================


def _validate_xpath_syntax(
    value: str,
) -> None:
    """Perform lightweight XPath validation.

    This is intentionally conservative.

    A complete XPath parser is unnecessary here because Selenium
    itself will perform the final validation against the browser.
    """

    stripped = value.strip()

    if not stripped:
        raise InvalidLocatorCandidate(
            "XPath value cannot be empty."
        )

    # Absolute XPath is deliberately rejected.
    if _ABSOLUTE_XPATH_RE.match(
        stripped
    ):
        raise InvalidLocatorCandidate(
            "Absolute XPath is not allowed."
        )

    # ------------------------------------------------------------
    # Balanced parentheses
    # ------------------------------------------------------------

    depth = 0
    quote: str | None = None

    escaped = False

    for char in stripped:

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if quote:

            if char == quote:
                quote = None

            continue

        if char in {
            "'",
            '"',
        }:

            quote = char
            continue

        if char == "(":
            depth += 1

        elif char == ")":

            depth -= 1

            if depth < 0:
                raise InvalidLocatorCandidate(
                    "XPath contains unmatched ')'."
                )

    if quote:
        raise InvalidLocatorCandidate(
            "XPath contains an unterminated quote."
        )

    if depth != 0:
        raise InvalidLocatorCandidate(
            "XPath contains unbalanced parentheses."
        )


# ================================================================
# MAIN VALIDATOR
# ================================================================


def validate_candidate(
    candidate: LocatorCandidate,
) -> LocatorCandidate:
    """Validate a Web/Selenium locator candidate.

    Checks:

        - strategy is supported
        - locator is not empty
        - locator length is reasonable
        - JavaScript is rejected
        - automation/Python code is rejected
        - CSS syntax is minimally sane
        - absolute XPath is rejected
        - XPath parentheses/quotes are balanced

    Returns:
        The same LocatorCandidate if valid.

    Raises:
        InvalidLocatorCandidate:
            If the candidate fails validation.

    Important:
        Passing this function does NOT mean the locator exists.

        The locator must still be tested against the live Selenium
        driver.
    """

    if candidate is None:
        raise InvalidLocatorCandidate(
            "Locator candidate cannot be None."
        )

    # ============================================================
    # STRATEGY
    # ============================================================

    strategy = (
        str(candidate.strategy)
        .strip()
        .lower()
    )

    if strategy not in SUPPORTED_STRATEGIES:

        raise InvalidLocatorCandidate(
            f"Unsupported locator strategy: {candidate.strategy}"
        )

    # ============================================================
    # VALUE
    # ============================================================

    if candidate.value is None:

        raise InvalidLocatorCandidate(
            "Locator value cannot be None."
        )

    value = str(
        candidate.value
    ).strip()

    if not value:

        raise InvalidLocatorCandidate(
            "Locator value cannot be empty."
        )

    # ============================================================
    # LENGTH
    # ============================================================

    if len(value) > MAX_LOCATOR_LENGTH:

        raise InvalidLocatorCandidate(
            f"Locator value is too long "
            f"(maximum {MAX_LOCATOR_LENGTH} characters)."
        )

    # ============================================================
    # CONTROL CHARACTERS
    # ============================================================

    # Reject NULL and other control characters that should never
    # appear in a locator.
    for char in value:

        if ord(char) < 32 and char not in {
            "\t",
            "\n",
            "\r",
        }:

            raise InvalidLocatorCandidate(
                "Locator contains invalid control characters."
            )

    # ============================================================
    # JAVASCRIPT
    # ============================================================

    if _JS_RE.search(value):

        raise InvalidLocatorCandidate(
            "Locator value appears to contain JavaScript."
        )

    # ============================================================
    # AUTOMATION CODE
    # ============================================================

    if _AUTOMATION_CODE_RE.search(value):

        raise InvalidLocatorCandidate(
            "Locator value appears to contain Selenium "
            "automation code instead of a locator."
        )

    # ============================================================
    # PYTHON / JAVASCRIPT CODE
    # ============================================================

    if _CODE_RE.search(value):

        raise InvalidLocatorCandidate(
            "Locator value appears to contain source code "
            "instead of a locator."
        )

    # ============================================================
    # STRATEGY-SPECIFIC VALIDATION
    # ============================================================

    if strategy == "xpath":

        _validate_xpath_syntax(
            value
        )

    elif strategy == "css":

        _validate_css_syntax(
            value
        )

    # ============================================================
    # NORMALIZE CANDIDATE VALUE
    # ============================================================

    # Keep the original candidate object but remove accidental
    # leading/trailing whitespace.
    candidate.value = value
    candidate.strategy = strategy

    return candidate


# ================================================================
# SAFE VALIDATION
# ================================================================


def is_valid_candidate(
    candidate: LocatorCandidate,
) -> bool:
    """Return True when a candidate passes local validation.

    This helper is useful when the caller does not want to catch
    InvalidLocatorCandidate manually.
    """

    try:

        validate_candidate(
            candidate
        )

        return True

    except InvalidLocatorCandidate:

        return False


# ================================================================
# BATCH VALIDATION
# ================================================================


def validate_candidates(
    candidates: list[LocatorCandidate],
) -> list[LocatorCandidate]:
    """Validate multiple candidates and discard invalid ones."""

    valid: list[LocatorCandidate] = []

    for candidate in candidates:
        try:
            validate_candidate(candidate)
            valid.append(candidate)

        except InvalidLocatorCandidate as exc:
            logger.debug(
                "Rejected invalid locator candidate: %s",
                exc,
            )

    return valid