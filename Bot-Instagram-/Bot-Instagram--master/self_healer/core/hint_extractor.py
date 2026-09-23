"""Extract locator hints and rank HTML chunks by relevance.

Supports:
    - XPath locators
    - CSS selectors

The extracted hints are intentionally generic so the same scoring
engine can be used by the Web/Selenium self-healer.

This module does NOT validate locators and does NOT interact with
Selenium directly. Its only responsibility is to extract useful
signals from a broken locator and rank sanitized HTML chunks before
they are sent to the healing engine / LLM provider.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)


# ================================================================
# CONSTANTS
# ================================================================

DEFAULT_TOP_K = 5
MAX_TOP_K = 50

# Attributes that are generally useful when repairing Web locators.
# Higher-priority attributes receive stronger scoring.
HIGH_VALUE_ATTRIBUTES = {
    "data-testid",
    "data-test",
    "data-qa",
    "data-cy",
    "data-testid",
    "aria-label",
    "aria-labelledby",
    "name",
    "placeholder",
    "title",
    "role",
    "id",
}

# Dynamic attributes that are normally poor locator signals.
LOW_VALUE_ATTRIBUTES = {
    "style",
    "onclick",
    "onchange",
    "oninput",
    "onmouseover",
    "tabindex",
}

# Common HTML tags that are especially relevant to user interaction.
INTERACTIVE_TAGS = {
    "a",
    "button",
    "input",
    "select",
    "textarea",
    "option",
    "label",
    "form",
}


# ================================================================
# TEXT NORMALIZATION
# ================================================================


def normalize_text(value: str) -> str:
    """Normalize text for comparison.

    Operations:
        - convert to string
        - lowercase
        - remove common broken-locator suffixes
        - remove accents
        - normalize repeated whitespace
        - trim surrounding whitespace
    """
    if value is None:
        return ""

    value = str(value).lower().strip()

    if not value:
        return ""

    # Remove typical broken locator suffixes.
    value = value.replace("___broken", "")
    value = value.replace("__broken", "")
    value = value.replace("_broken", "")

    # Remove accents.
    value = unicodedata.normalize("NFD", value)
    value = "".join(
        char
        for char in value
        if unicodedata.category(char) != "Mn"
    )

    # Normalize whitespace.
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def _unique_preserve_order(values: list[Any]) -> list[Any]:
    """Remove duplicates while preserving insertion order."""
    result: list[Any] = []
    seen: set[str] = set()

    for value in values:
        key = repr(value)

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


# ================================================================
# HTML ATTRIBUTE HELPERS
# ================================================================


def _normalize_attribute_value(value: str) -> str:
    """Normalize an HTML attribute value for comparison."""
    return normalize_text(value)


def _attribute_matches(
    chunk: str,
    attribute: str,
    value: str,
) -> bool:
    """Check whether an HTML chunk contains an attribute/value pair.

    Supports:
        data-testid="login"
        data-testid='login'
        data-testid=login

    Matching is case-insensitive for the attribute name and
    normalized for the value.
    """
    if not chunk or not attribute or value is None:
        return False

    attribute = str(attribute).strip()
    value = str(value).strip()

    if not attribute or not value:
        return False

    escaped_attr = re.escape(attribute)
    escaped_value = re.escape(value)

    # Quoted attribute.
    quoted_pattern = (
        rf"\b{escaped_attr}\s*=\s*"
        rf"""(["']){escaped_value}\1"""
    )

    if re.search(
        quoted_pattern,
        chunk,
        flags=re.IGNORECASE,
    ):
        return True

    # Unquoted attribute.
    unquoted_pattern = (
        rf"\b{escaped_attr}\s*=\s*"
        rf"{escaped_value}"
        rf"(?=\s|/?>)"
    )

    if re.search(
        unquoted_pattern,
        chunk,
        flags=re.IGNORECASE,
    ):
        return True

    # Normalized comparison for quoted values. This handles
    # differences such as:
    #
    #   "Sign   In"
    #   "sign in"
    #
    attribute_pattern = re.compile(
        rf"\b{escaped_attr}\s*=\s*"
        rf"""(["'])(.*?)\1""",
        flags=re.IGNORECASE | re.DOTALL,
    )

    target = _normalize_attribute_value(value)

    for match in attribute_pattern.finditer(chunk):
        actual = _normalize_attribute_value(
            match.group(2)
        )

        if actual == target:
            return True

    return False


def _extract_html_attribute_values(
    chunk: str,
    attribute: str,
) -> list[str]:
    """Extract quoted and unquoted values of one HTML attribute."""
    if not chunk or not attribute:
        return []

    escaped_attr = re.escape(attribute)

    values: list[str] = []

    # Quoted values.
    quoted_pattern = re.compile(
        rf"\b{escaped_attr}\s*=\s*"
        rf"""(["'])(.*?)\1""",
        flags=re.IGNORECASE | re.DOTALL,
    )

    for match in quoted_pattern.finditer(chunk):
        values.append(match.group(2))

    # Unquoted values.
    unquoted_pattern = re.compile(
        rf"\b{escaped_attr}\s*=\s*"
        rf"""([^\s"'=<>`]+)""",
        flags=re.IGNORECASE,
    )

    for match in unquoted_pattern.finditer(chunk):
        value = match.group(1)

        if value not in values:
            values.append(value)

    return values


# ================================================================
# XPATH HINT EXTRACTION
# ================================================================


def extract_xpath_hints(
    broken_xpath: str,
) -> dict[str, Any]:
    """Extract searchable hints from a broken XPath.

    Extracts:
        - tags
        - roles
        - text values
        - attributes
        - IDs
        - classes
        - normalized text values
    """
    hints: dict[str, Any] = {
        "raw_locator": broken_xpath,
        "locator_type": "xpath",
        "raw_xpath": broken_xpath,
        "texts": [],
        "normalized_texts": [],
        "roles": [],
        "tags": [],
        "attributes": {},
        "ids": [],
        "classes": [],
        "attribute_selectors": [],
    }

    if not broken_xpath:
        return hints

    xpath = str(broken_xpath).strip()

    if not xpath:
        return hints

    # ------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------

    tags = re.findall(
        r"//([a-zA-Z][a-zA-Z0-9_-]*)",
        xpath,
    )

    # Also support simple absolute XPath:
    #
    # /html/body/div
    #
    if not tags:
        tags = re.findall(
            r"/([a-zA-Z][a-zA-Z0-9_-]*)",
            xpath,
        )

    hints["tags"] = _unique_preserve_order(
        [
            tag.lower()
            for tag in tags
            if tag
        ]
    )

    # ------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------

    roles = re.findall(
        r"@role\s*=\s*(['\"])(.*?)\1",
        xpath,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for _, role in roles:
        normalized = normalize_text(role)

        if normalized:
            hints["roles"].append(
                normalized
            )

    # ------------------------------------------------------------
    # Text from normalize-space()
    # ------------------------------------------------------------

    normalize_text_patterns = [
        re.compile(
            r"normalize-space\s*\(\s*(?:\.|text\s*\(\s*\))?\s*\)"
            r"\s*=\s*(['\"])(.*?)\1",
            flags=re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"normalize-space\s*\(\s*\)"
            r"\s*=\s*(['\"])(.*?)\1",
            flags=re.IGNORECASE | re.DOTALL,
        ),
    ]

    for pattern in normalize_text_patterns:
        for _, text in pattern.findall(xpath):
            if text:
                hints["texts"].append(text)

    # ------------------------------------------------------------
    # text() = "..."
    # ------------------------------------------------------------

    text_nodes = re.findall(
        r"text\s*\(\s*\)"
        r"\s*=\s*(['\"])(.*?)\1",
        xpath,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for _, text in text_nodes:
        if text:
            hints["texts"].append(text)

    # ------------------------------------------------------------
    # contains(text(), "...")
    # contains(., "...")
    # contains(normalize-space(), "...")
    # ------------------------------------------------------------

    contains_texts = re.findall(
        r"contains\s*\(\s*"
        r"(?:"
        r"text\s*\(\s*\)"
        r"|"
        r"\."
        r"|"
        r"normalize-space\s*\(\s*\)"
        r")"
        r"\s*,\s*"
        r"(['\"])(.*?)\1"
        r"\s*\)",
        xpath,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for _, text in contains_texts:
        if text:
            hints["texts"].append(text)

    # ------------------------------------------------------------
    # Generic @attribute="value"
    # ------------------------------------------------------------

    attrs = re.findall(
        r"@([a-zA-Z_:][a-zA-Z0-9_:\-]*)"
        r"\s*=\s*"
        r"(['\"])(.*?)\2",
        xpath,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for key, _, value in attrs:
        key = key.lower().strip()

        if not key or key == "role":
            continue

        if not value:
            continue

        # Preserve the first exact value.
        if key not in hints["attributes"]:
            hints["attributes"][key] = value

        if key == "id":
            hints["ids"].append(value)

        elif key == "class":
            hints["classes"].extend(
                value.split()
            )

    # ------------------------------------------------------------
    # contains(@attribute, "value")
    # ------------------------------------------------------------

    contains_attrs = re.findall(
        r"contains\s*\(\s*"
        r"@([a-zA-Z_:][a-zA-Z0-9_:\-]*)"
        r"\s*,\s*"
        r"(['\"])(.*?)\2"
        r"\s*\)",
        xpath,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for key, _, value in contains_attrs:
        key = key.lower().strip()

        if not key or not value:
            continue

        # Do not overwrite exact attributes.
        if key not in hints["attributes"]:
            hints["attributes"][key] = value

    # ------------------------------------------------------------
    # Predicates using text containment in another form.
    # ------------------------------------------------------------

    text_contains = re.findall(
        r"contains\s*\(\s*"
        r"(?:"
        r"normalize-space\s*\(\s*(?:\.|text\s*\(\s*\))?\s*\)"
        r"|text\s*\(\s*\)"
        r"|."
        r")"
        r"\s*,\s*"
        r"(['\"])(.*?)\1",
        xpath,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for _, text in text_contains:
        normalized = normalize_text(text)

        if (
            normalized
            and len(normalized) >= 2
            and normalized not in {
                normalize_text(existing)
                for existing in hints["texts"]
            }
        ):
            hints["texts"].append(text)

    # ------------------------------------------------------------
    # Normalize and deduplicate.
    # ------------------------------------------------------------

    hints["texts"] = _unique_preserve_order(
        [
            text
            for text in hints["texts"]
            if text
        ]
    )

    hints["normalized_texts"] = _unique_preserve_order(
        [
            normalize_text(text)
            for text in hints["texts"]
            if normalize_text(text)
        ]
    )

    hints["roles"] = _unique_preserve_order(
        [
            normalize_text(role)
            for role in hints["roles"]
            if normalize_text(role)
        ]
    )

    hints["ids"] = _unique_preserve_order(
        [
            value
            for value in hints["ids"]
            if value
        ]
    )

    hints["classes"] = _unique_preserve_order(
        [
            value
            for value in hints["classes"]
            if value
        ]
    )

    return hints


# ================================================================
# CSS PARSER HELPERS
# ================================================================


def _mask_css_strings(
    css: str,
) -> tuple[str, list[str]]:
    """Replace CSS quoted strings with placeholders.

    This allows tag/class/id extraction without accidentally
    interpreting values such as:

        [data-label="button"]

    as actual CSS tags.
    """
    strings: list[str] = []

    result: list[str] = []

    index = 0
    length = len(css)

    while index < length:

        char = css[index]

        if char not in {"'", '"'}:
            result.append(char)
            index += 1
            continue

        quote = char
        start = index
        index += 1

        escaped = False

        while index < length:
            current = css[index]

            if escaped:
                escaped = False
                index += 1
                continue

            if current == "\\":
                escaped = True
                index += 1
                continue

            if current == quote:
                index += 1
                break

            index += 1

        strings.append(
            css[start:index]
        )

        placeholder = (
            f"__CSS_STRING_{len(strings) - 1}__"
        )

        result.append(placeholder)

    return "".join(result), strings


def _extract_css_attribute_selectors(
    css: str,
) -> list[dict[str, Any]]:
    """Extract CSS attribute selectors.

    Supports:

        [disabled]
        [name="username"]
        [data-testid='login']
        [data-action*="login"]
        [class~="primary"]
    """
    selectors: list[dict[str, Any]] = []

    pattern = re.compile(
        r"\[\s*"
        r"([a-zA-Z_:][a-zA-Z0-9_:\-]*)"
        r"\s*"
        r"(?:(\*=|\^=|\$=|~=|\|=|!=|=)"
        r"\s*"
        r"(?:"
        r"(['\"])(.*?)\3"
        r"|"
        r"([^\]\s]+)"
        r")"
        r")?"
        r"\s*\]",
        flags=re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(css):

        attribute = match.group(1).lower()
        operator = match.group(2)

        quoted_value = match.group(4)
        unquoted_value = match.group(5)

        value = (
            quoted_value
            if quoted_value is not None
            else unquoted_value
        )

        selectors.append(
            {
                "attribute": attribute,
                "operator": operator,
                "value": value,
            }
        )

    return selectors


# ================================================================
# CSS HINT EXTRACTION
# ================================================================


def extract_css_hints(
    broken_css: str,
) -> dict[str, Any]:
    """Extract searchable hints from a CSS selector.

    Supports selectors such as:

        button
        button.login
        #login
        .submit-button
        input[name="username"]
        button[data-testid="login"]
        [aria-label="Login"]
        div.container button.primary
        input[type^="pass"]
        [data-action*="login"]

    CSS cannot reliably represent visible text, so this function
    intentionally does not invent text hints.
    """
    hints: dict[str, Any] = {
        "raw_locator": broken_css,
        "locator_type": "css",
        "raw_css": broken_css,
        "texts": [],
        "normalized_texts": [],
        "roles": [],
        "tags": [],
        "attributes": {},
        "ids": [],
        "classes": [],
        "attribute_selectors": [],
    }

    if not broken_css:
        return hints

    css = str(broken_css).strip()

    if not css:
        return hints

    # ------------------------------------------------------------
    # Attribute selectors.
    # ------------------------------------------------------------

    attribute_selectors = _extract_css_attribute_selectors(
        css
    )

    hints["attribute_selectors"] = (
        attribute_selectors
    )

    # ------------------------------------------------------------
    # Generic attribute hints.
    #
    # Keep values from CSS attribute selectors.
    # ------------------------------------------------------------

    for selector in attribute_selectors:

        attribute = selector.get("attribute")
        value = selector.get("value")

        if not attribute or value is None:
            continue

        if attribute not in hints["attributes"]:
            hints["attributes"][attribute] = value

        if attribute == "id":
            hints["ids"].append(value)

        elif attribute == "class":
            hints["classes"].extend(
                str(value).split()
            )

        elif attribute == "role":
            normalized_role = normalize_text(
                str(value)
            )

            if normalized_role:
                hints["roles"].append(
                    normalized_role
                )

    # ------------------------------------------------------------
    # Remove quoted strings so IDs/classes/tags are not extracted
    # from attribute values.
    # ------------------------------------------------------------

    masked_css, _ = _mask_css_strings(css)

    # Remove attribute selector contents completely.
    selector_structure = re.sub(
        r"\[[^\]]*\]",
        " ",
        masked_css,
    )

    # ------------------------------------------------------------
    # IDs
    # ------------------------------------------------------------

    ids = re.findall(
        r"#([a-zA-Z_][a-zA-Z0-9_-]*)",
        selector_structure,
    )

    hints["ids"].extend(ids)

    # ------------------------------------------------------------
    # Classes
    # ------------------------------------------------------------

    classes = re.findall(
        r"\.([a-zA-Z_][a-zA-Z0-9_-]*)",
        selector_structure,
    )

    hints["classes"].extend(classes)

    # ------------------------------------------------------------
    # Tags
    #
    # Avoid:
    #   .class
    #   #id
    #   pseudo classes
    #   CSS function names
    # ------------------------------------------------------------

    tag_pattern = re.compile(
        r"(?<![#.\w-])"
        r"([a-zA-Z][a-zA-Z0-9_-]*)"
        r"(?![\w-])"
    )

    for match in tag_pattern.finditer(
        selector_structure
    ):

        start = match.start()

        previous_char = (
            selector_structure[start - 1]
            if start > 0
            else ""
        )

        # Ignore pseudo selector/function names:
        #
        # :not(...)
        # :has(...)
        # :is(...)
        # :where(...)
        #
        if previous_char == ":":
            continue

        tag = match.group(1).lower()

        # Ignore common CSS keywords/functions.
        if tag in {
            "not",
            "has",
            "is",
            "where",
            "nth-child",
            "nth-of-type",
            "first-child",
            "last-child",
            "only-child",
            "first-of-type",
            "last-of-type",
            "only-of-type",
            "root",
            "empty",
            "checked",
            "disabled",
            "enabled",
            "required",
            "optional",
            "selected",
            "focus",
            "hover",
            "active",
        }:
            continue

        # Ignore CSS string placeholders.
        if tag.startswith("css_string_"):
            continue

        hints["tags"].append(tag)

    # ------------------------------------------------------------
    # Deduplicate.
    # ------------------------------------------------------------

    hints["ids"] = _unique_preserve_order(
        [
            value
            for value in hints["ids"]
            if value
        ]
    )

    hints["classes"] = _unique_preserve_order(
        [
            value
            for value in hints["classes"]
            if value
        ]
    )

    hints["tags"] = _unique_preserve_order(
        [
            value
            for value in hints["tags"]
            if value
        ]
    )

    hints["roles"] = _unique_preserve_order(
        [
            normalize_text(role)
            for role in hints["roles"]
            if normalize_text(role)
        ]
    )

    return hints


# ================================================================
# CSS ATTRIBUTE SCORING
# ================================================================


def _score_attribute_selector(
    chunk: str,
    attribute_selector: dict[str, Any],
) -> float:
    """Score a CSS attribute selector against an HTML chunk."""
    if not chunk or not attribute_selector:
        return 0.0

    attribute = attribute_selector.get(
        "attribute"
    )
    operator = attribute_selector.get(
        "operator"
    )
    value = attribute_selector.get(
        "value"
    )

    if not attribute:
        return 0.0

    attribute = str(attribute).lower()

    # Presence selector:
    #
    # [disabled]
    #
    if value is None:

        pattern = (
            rf"\b{re.escape(attribute)}"
            rf"(?=\s|=|/?>)"
        )

        return (
            25.0
            if re.search(
                pattern,
                chunk,
                flags=re.IGNORECASE,
            )
            else 0.0
        )

    value = str(value)

    if not value:
        return 0.0

    actual_values = _extract_html_attribute_values(
        chunk,
        attribute,
    )

    if not actual_values:
        return 0.0

    target = normalize_text(value)

    if not target:
        return 0.0

    # Attribute importance.
    if attribute == "id":
        exact_weight = 65.0
        partial_weight = 42.0

    elif attribute.startswith("data-"):
        exact_weight = 55.0
        partial_weight = 36.0

    elif attribute.startswith("aria-"):
        exact_weight = 50.0
        partial_weight = 34.0

    elif attribute in {
        "name",
        "placeholder",
        "title",
        "role",
    }:
        exact_weight = 50.0
        partial_weight = 32.0

    elif attribute in LOW_VALUE_ATTRIBUTES:
        exact_weight = 12.0
        partial_weight = 8.0

    else:
        exact_weight = 32.0
        partial_weight = 22.0

    for actual in actual_values:

        actual_norm = normalize_text(actual)

        if not actual_norm:
            continue

        # Exact match.
        if operator in {None, "="}:
            if actual_norm == target:
                return exact_weight

        # Contains.
        elif operator == "*=":
            if target in actual_norm:
                return partial_weight

        # Prefix.
        elif operator == "^=":
            if actual_norm.startswith(target):
                return partial_weight

        # Suffix.
        elif operator == "$=":
            if actual_norm.endswith(target):
                return partial_weight

        # CSS class token.
        elif operator == "~=":
            if target in actual_norm.split():
                return partial_weight

        # Language / hyphen prefix.
        elif operator == "|=":
            if (
                actual_norm == target
                or actual_norm.startswith(
                    target + "-"
                )
            ):
                return partial_weight

        # Non-standard inequality selector.
        elif operator == "!=":
            if actual_norm != target:
                return 10.0

    return 0.0


# ================================================================
# TEXT SCORING
# ================================================================


def _extract_visible_text_fragments(
    chunk: str,
) -> list[str]:
    """Extract simple visible-text fragments from HTML.

    This is intentionally lightweight. The actual DOM remains the
    source of truth during candidate validation.
    """
    if not chunk:
        return []

    fragments = re.findall(
        r">([^<>]{2,200})<",
        chunk,
    )

    return [
        fragment.strip()
        for fragment in fragments
        if fragment.strip()
    ]


def _score_text_hints(
    chunk: str,
    hints: dict[str, Any],
) -> float:
    """Score XPath text hints against an HTML chunk."""
    normalized_texts = hints.get(
        "normalized_texts",
        [],
    )

    if not normalized_texts:
        return 0.0

    score = 0.0

    visible_fragments = (
        _extract_visible_text_fragments(
            chunk
        )
    )

    normalized_fragments = [
        normalize_text(fragment)
        for fragment in visible_fragments
    ]

    for text in normalized_texts:

        if not text:
            continue

        # Strong exact occurrence.
        if text in normalize_text(chunk):
            score += 100.0

        # Word-level evidence.
        words = [
            word
            for word in text.split()
            if len(word) >= 2
        ]

        for word in words:
            if word in normalize_text(chunk):
                score += 10.0

        # Fuzzy visible-text comparison.
        if len(text) < 4:
            continue

        best_ratio = 0.0

        for candidate in normalized_fragments:

            if not candidate:
                continue

            ratio = SequenceMatcher(
                None,
                text,
                candidate,
            ).ratio()

            if ratio > best_ratio:
                best_ratio = ratio

        if best_ratio >= 0.80:
            score += best_ratio * 80.0

    return score


# ================================================================
# ROLE SCORING
# ================================================================


def _score_roles(
    chunk: str,
    hints: dict[str, Any],
) -> float:
    """Score ARIA role hints."""
    score = 0.0

    for role in hints.get("roles", []):

        role_norm = normalize_text(role)

        if not role_norm:
            continue

        values = _extract_html_attribute_values(
            chunk,
            "role",
        )

        for value in values:

            if normalize_text(value) == role_norm:
                score += 50.0
                break

    return score


# ================================================================
# TAG SCORING
# ================================================================


def _score_tags(
    chunk: str,
    hints: dict[str, Any],
) -> float:
    """Score HTML tag hints."""
    if not chunk:
        return 0.0

    score = 0.0

    for tag in hints.get("tags", []):

        tag_norm = normalize_text(tag)

        if not tag_norm:
            continue

        pattern = (
            rf"<{re.escape(tag_norm)}"
            rf"(?:\s|>|/>)"
        )

        if re.search(
            pattern,
            chunk,
            flags=re.IGNORECASE,
        ):
            score += 20.0

            if tag_norm in INTERACTIVE_TAGS:
                score += 5.0

    return score


# ================================================================
# ID SCORING
# ================================================================


def _score_ids(
    chunk: str,
    hints: dict[str, Any],
) -> float:
    """Score ID hints."""
    score = 0.0

    for element_id in hints.get(
        "ids",
        [],
    ):

        if not element_id:
            continue

        if _attribute_matches(
            chunk,
            "id",
            str(element_id),
        ):
            score += 65.0

    return score


# ================================================================
# CLASS SCORING
# ================================================================


def _score_classes(
    chunk: str,
    hints: dict[str, Any],
) -> float:
    """Score class-token hints."""
    score = 0.0

    class_values = _extract_html_attribute_values(
        chunk,
        "class",
    )

    if not class_values:
        return 0.0

    actual_classes: set[str] = set()

    for value in class_values:
        actual_classes.update(
            token
            for token in str(value).split()
            if token
        )

    for class_name in hints.get(
        "classes",
        [],
    ):

        if not class_name:
            continue

        if class_name in actual_classes:
            score += 22.0

    return score


# ================================================================
# GENERIC ATTRIBUTE SCORING
# ================================================================


def _score_generic_attributes(
    chunk: str,
    hints: dict[str, Any],
) -> float:
    """Score generic XPath attribute hints."""
    score = 0.0

    for attr, value in hints.get(
        "attributes",
        {},
    ).items():

        if not attr or value is None:
            continue

        attr = str(attr).lower()

        # These are scored independently elsewhere.
        if attr in {
            "id",
            "class",
            "role",
        }:
            continue

        if attr in LOW_VALUE_ATTRIBUTES:
            continue

        if _attribute_matches(
            chunk,
            attr,
            str(value),
        ):
            if attr.startswith("data-"):
                score += 40.0

            elif attr.startswith("aria-"):
                score += 38.0

            elif attr in {
                "name",
                "placeholder",
                "title",
            }:
                score += 38.0

            else:
                score += 25.0

    return score


# ================================================================
# CHUNK SCORING
# ================================================================


def score_chunk(
    chunk: str,
    hints: dict[str, Any],
) -> float:
    """Score an HTML chunk based on extracted locator hints.

    The scoring is heuristic. Its purpose is to select relevant HTML
    chunks before sending them to the LLM.

    This function does NOT determine whether a locator is valid.
    Candidate validation must still happen against the live Selenium
    DOM.
    """
    if not chunk or not hints:
        return 0.0

    score = 0.0

    # Text.
    score += _score_text_hints(
        chunk,
        hints,
    )

    # ARIA roles.
    score += _score_roles(
        chunk,
        hints,
    )

    # Tags.
    score += _score_tags(
        chunk,
        hints,
    )

    # IDs.
    score += _score_ids(
        chunk,
        hints,
    )

    # Classes.
    score += _score_classes(
        chunk,
        hints,
    )

    # XPath generic attributes.
    score += _score_generic_attributes(
        chunk,
        hints,
    )

    # CSS attribute selectors.
    #
    # Apply these with a small correction because exact attribute
    # matches may already be represented in hints["attributes"].
    for attribute_selector in hints.get(
        "attribute_selectors",
        [],
    ):

        selector_score = _score_attribute_selector(
            chunk,
            attribute_selector,
        )

        if selector_score <= 0:
            continue

        attribute = str(
            attribute_selector.get(
                "attribute",
                "",
            )
        ).lower()

        # Avoid excessive double-counting for the strongest
        # attributes while retaining CSS selector evidence.
        if attribute == "id":
            score += selector_score * 0.60

        elif attribute in {
            "class",
            "role",
        }:
            score += selector_score * 0.65

        else:
            score += selector_score * 0.80

    return float(score)


# ================================================================
# LOCATOR TYPE DETECTION
# ================================================================


def detect_locator_type(
    locator: str,
) -> str:
    """Detect whether a locator is XPath or CSS.

    Returns:
        "xpath" or "css"

    The detector intentionally favors XPath only when there are
    strong XPath-specific signals.
    """
    if not locator:
        return "css"

    value = str(locator).strip()

    if not value:
        return "css"

    # Common XPath roots.
    if (
        value.startswith("/")
        or value.startswith("./")
        or value.startswith(".//")
        or value.startswith("(")
    ):
        return "xpath"

    # XPath axes.
    if re.search(
        r"//"
        r"|"
        r"/(?:ancestor|ancestor-or-self|attribute|child|descendant"
        r"|descendant-or-self|following|following-sibling|parent"
        r"|preceding|preceding-sibling|self)::",
        value,
        flags=re.IGNORECASE,
    ):
        return "xpath"

    # XPath functions / expressions.
    if re.search(
        r"^(?:"
        r"contains"
        r"|starts-with"
        r"|substring"
        r"|substring-before"
        r"|substring-after"
        r"|normalize-space"
        r"|text"
        r"|count"
        r"|position"
        r"|last"
        r")\s*\(",
        value,
        flags=re.IGNORECASE,
    ):
        return "xpath"

    # XPath attribute references.
    if re.search(
        r"@\w+",
        value,
        flags=re.IGNORECASE,
    ):
        return "xpath"

    # XPath node functions.
    if re.search(
        r"\btext\s*\(\s*\)"
        r"|"
        r"\bnormalize-space\s*\(",
        value,
        flags=re.IGNORECASE,
    ):
        return "xpath"

    # XPath predicates attached to a path.
    if re.search(
        r"//[^/]+\[[^\]]+\]",
        value,
        flags=re.IGNORECASE,
    ):
        return "xpath"

    return "css"


# ================================================================
# CHUNK SELECTION
# ================================================================


def _normalize_top_k(
    top_k: int,
) -> int:
    """Normalize ranking limit."""
    try:
        value = int(top_k)
    except (TypeError, ValueError):
        value = DEFAULT_TOP_K

    return min(
        max(value, 1),
        MAX_TOP_K,
    )


def _expand_with_neighbors(
    ranked_items: list[dict[str, Any]],
    chunks: list[str],
    top_k: int,
) -> list[int]:
    """Select top-ranked chunks and their immediate neighbors.

    The resulting indexes are ordered primarily by relevance rather
    than by accidental insertion order.
    """
    if not ranked_items:
        return []

    selected: set[int] = set()

    for item in ranked_items[:top_k]:

        index = int(item["index"])

        selected.add(index)

        if index > 0:
            selected.add(index - 1)

        if index + 1 < len(chunks):
            selected.add(index + 1)

    # Keep selected chunks ordered by:
    #   1. score descending
    #   2. original document position
    #
    # This means a high-confidence chunk remains near the front even
    # when its neighboring chunks were also included.
    score_by_index = {
        int(item["index"]): float(
            item.get("score", 0.0)
        )
        for item in ranked_items
    }

    return sorted(
        selected,
        key=lambda index: (
            -score_by_index.get(index, 0.0),
            index,
        ),
    )


# ================================================================
# RANK CHUNKS
# ================================================================


def rank_chunks_by_locator_hints(
    chunks: list[str],
    broken_locator: str,
    top_k: int = DEFAULT_TOP_K,
    include_neighbors: bool = True,
) -> list[dict[str, Any]]:
    """Rank HTML chunks by relevance to a broken Web locator.

    Supports both XPath and CSS selectors.

    Args:
        chunks:
            List of sanitized HTML chunks.

        broken_locator:
            Original broken XPath or CSS selector.

        top_k:
            Number of strongest chunks to select before neighbor
            expansion.

        include_neighbors:
            Whether to include adjacent chunks for structural
            context.

    Returns:
        A list of dictionaries:

            {
                "index": int,
                "chunk": str,
                "score": float,
            }
    """
    if not chunks:
        logger.debug(
            "No HTML chunks provided."
        )
        return []

    # Normalize malformed/non-string chunks without crashing the
    # healing pipeline.
    normalized_chunks = [
        chunk
        if isinstance(chunk, str)
        else str(chunk or "")
        for chunk in chunks
    ]

    top_k = _normalize_top_k(top_k)

    if not broken_locator:
        logger.debug(
            "No broken locator provided. "
            "Returning fallback HTML context."
        )

        fallback_count = min(
            top_k,
            len(normalized_chunks),
        )

        return [
            {
                "index": index,
                "chunk": normalized_chunks[index],
                "score": 0.0,
            }
            for index in range(fallback_count)
        ]

    locator = str(
        broken_locator
    ).strip()

    if not locator:
        fallback_count = min(
            top_k,
            len(normalized_chunks),
        )

        return [
            {
                "index": index,
                "chunk": normalized_chunks[index],
                "score": 0.0,
            }
            for index in range(fallback_count)
        ]

    locator_type = detect_locator_type(
        locator
    )

    # ============================================================
    # EXTRACT HINTS
    # ============================================================

    try:

        if locator_type == "xpath":

            hints = extract_xpath_hints(
                locator
            )

            logger.debug(
                "Extracted XPath hints: %s",
                {
                    key: value
                    for key, value in hints.items()
                    if key not in {
                        "raw_locator",
                        "raw_xpath",
                    }
                },
            )

        else:

            hints = extract_css_hints(
                locator
            )

            logger.debug(
                "Extracted CSS hints: %s",
                {
                    key: value
                    for key, value in hints.items()
                    if key not in {
                        "raw_locator",
                        "raw_css",
                    }
                },
            )

    except Exception as exc:

        logger.exception(
            "Failed to extract %s hints from locator %r: %s",
            locator_type,
            locator,
            exc,
        )

        hints = {
            "raw_locator": locator,
            "locator_type": locator_type,
            "texts": [],
            "normalized_texts": [],
            "roles": [],
            "tags": [],
            "attributes": {},
            "ids": [],
            "classes": [],
            "attribute_selectors": [],
        }

    # ============================================================
    # SCORE EVERY CHUNK
    # ============================================================

    scored: list[dict[str, Any]] = []

    for index, chunk in enumerate(
        normalized_chunks
    ):

        if not chunk:
            continue

        try:

            score = score_chunk(
                chunk,
                hints,
            )

        except Exception as exc:

            logger.warning(
                "Failed to score HTML chunk %s: %s",
                index,
                exc,
            )

            score = 0.0

        scored.append(
            {
                "index": index,
                "score": float(score),
                "chunk": chunk,
            }
        )

    # ============================================================
    # SORT BY RELEVANCE
    # ============================================================

    scored.sort(
        key=lambda item: (
            -float(item["score"]),
            int(item["index"]),
        )
    )

    logger.debug(
        "Top chunks by %s locator score: %s",
        locator_type,
        [
            (
                item["index"],
                item["score"],
            )
            for item in scored[:top_k]
        ],
    )

    # ============================================================
    # SELECT TOP CHUNKS + OPTIONAL NEIGHBORS
    # ============================================================

    if include_neighbors:

        selected_indexes = _expand_with_neighbors(
            scored,
            normalized_chunks,
            top_k,
        )

    else:

        selected_indexes = [
            int(item["index"])
            for item in scored[:top_k]
        ]

    # ============================================================
    # FALLBACK
    # ============================================================

    if not selected_indexes:

        logger.debug(
            "No chunks matched locator hints. "
            "Falling back to first %s chunks.",
            top_k,
        )

        selected_indexes = list(
            range(
                min(
                    top_k,
                    len(normalized_chunks),
                )
            )
        )

    # Prevent excessive context expansion.
    max_results = min(
        len(normalized_chunks),
        max(
            1,
            top_k * 3,
        ),
    )

    selected_indexes = selected_indexes[
        :max_results
    ]

    # ============================================================
    # BUILD SCORE LOOKUP
    # ============================================================

    score_by_index = {
        int(item["index"]): float(
            item["score"]
        )
        for item in scored
    }

    # ============================================================
    # BUILD RESULT
    # ============================================================

    result: list[dict[str, Any]] = []

    for index in selected_indexes:

        if index < 0 or index >= len(
            normalized_chunks
        ):
            continue

        result.append(
            {
                "index": index,
                "chunk": normalized_chunks[index],
                "score": score_by_index.get(
                    index,
                    0.0,
                ),
            }
        )

    logger.debug(
        "Selected %d HTML chunks for LLM processing.",
        len(result),
    )

    return result


# ================================================================
# BACKWARD COMPATIBILITY
# ================================================================


def rank_chunks_by_xpath_hints(
    chunks: list[str],
    broken_xpath: str,
    top_k: int = DEFAULT_TOP_K,
    include_neighbors: bool = True,
) -> list[dict[str, Any]]:
    """Backward-compatible XPath ranking wrapper."""
    return rank_chunks_by_locator_hints(
        chunks=chunks,
        broken_locator=broken_xpath,
        top_k=top_k,
        include_neighbors=include_neighbors,
    )


# ================================================================
# CSS-SPECIFIC WRAPPER
# ================================================================


def rank_chunks_by_css_hints(
    chunks: list[str],
    broken_css: str,
    top_k: int = DEFAULT_TOP_K,
    include_neighbors: bool = True,
) -> list[dict[str, Any]]:
    """Convenience wrapper for CSS selector ranking."""
    return rank_chunks_by_locator_hints(
        chunks=chunks,
        broken_locator=broken_css,
        top_k=top_k,
        include_neighbors=include_neighbors,
    )
