"""HTML sanitization before sending content to an AI provider.

The sanitizer removes executable/non-structural HTML, keeps attributes
that are useful for Web/Selenium locator generation, and redacts values
that may contain credentials, tokens, personal data, or other secrets.
"""

from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser

from .exceptions import HtmlSanitizationError


# Elements that provide little or no value for locator generation and may
# contain executable code, embedded documents, or very large content.
DROP_TAGS = {
    "script",
    "style",
    "svg",
    "canvas",
    "iframe",
    "noscript",
    "object",
    "embed",
    "template",
}


# HTML void elements do not have closing tags.
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


# Attributes useful for Web/Selenium locator generation.
#
# data-* is handled separately because modern web applications frequently
# use custom test/automation attributes.
ALLOWED_ATTRS = {
    "id",
    "class",
    "name",
    "type",
    "role",
    "aria-label",
    "aria-labelledby",
    "aria-describedby",
    "aria-controls",
    "aria-current",
    "aria-expanded",
    "aria-haspopup",
    "aria-hidden",
    "aria-selected",
    "aria-checked",
    "aria-disabled",
    "aria-pressed",
    "aria-required",
    "aria-valuenow",
    "aria-valuemin",
    "aria-valuemax",
    "aria-placeholder",
    "placeholder",
    "title",
    "alt",
    "href",
    "value",
}


# ----------------------------------------------------------------------
# Sensitive-data patterns
# ----------------------------------------------------------------------

EMAIL_RE = re.compile(
    r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"
)


LONG_NUMBER_RE = re.compile(
    r"\b\d{12,}\b"
)


JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]+"
    r"\.[A-Za-z0-9_-]+"
    r"\.[A-Za-z0-9_-]+\b"
)


BEARER_RE = re.compile(
    r"\bBearer\s+[A-Za-z0-9._+/=-]{8,}\b",
    re.IGNORECASE,
)


# Detect common key/value secret patterns in text and attributes.
#
# Examples:
#   api_key=abc123
#   api-key: abc123
#   token=abc123
#   password=abc123
#   authorization: Bearer abc123
#
# The expression intentionally stops at whitespace and HTML delimiters.
SECRET_KV_RE = re.compile(
    r"\b(?:"
    r"api[-_ ]?key"
    r"|secret"
    r"|password"
    r"|passwd"
    r"|token"
    r"|access[-_ ]?token"
    r"|refresh[-_ ]?token"
    r"|auth[-_ ]?token"
    r"|authorization"
    r"|cookie"
    r")"
    r"\s*(?:=|:)\s*"
    r"([^\s<>\"]+)",
    re.IGNORECASE,
)


# Attribute names that should never expose their value to the model.
SENSITIVE_ATTRIBUTE_NAMES = {
    "password",
    "passwd",
    "secret",
    "token",
    "access-token",
    "access_token",
    "refresh-token",
    "refresh_token",
    "auth-token",
    "auth_token",
    "api-key",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "set-cookie",
}


SENSITIVE_ATTRIBUTE_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
)


def _mask_sensitive_text(value: str) -> str:
    """Redact sensitive values from text or attribute content."""
    if value is None:
        return ""

    masked = html_lib.unescape(str(value))

    masked = EMAIL_RE.sub(
        "[REDACTED_EMAIL]",
        masked,
    )

    masked = JWT_RE.sub(
        "[REDACTED_JWT]",
        masked,
    )

    masked = BEARER_RE.sub(
        "[REDACTED_BEARER]",
        masked,
    )

    masked = SECRET_KV_RE.sub(
        lambda match: (
            match.group(0)[: match.group(0).find(
                match.group(1)
            )]
            + "[REDACTED_SECRET]"
        ),
        masked,
    )

    masked = LONG_NUMBER_RE.sub(
        "[REDACTED_NUMBER]",
        masked,
    )

    return masked


def _attribute_is_sensitive(
    tag: str,
    attrs: list[tuple[str, str | None]],
    name: str,
) -> bool:
    """Determine whether an HTML attribute value should be redacted."""
    normalized_name = name.lower().strip()

    if normalized_name in SENSITIVE_ATTRIBUTE_NAMES:
        return True

    # data-token, data-password, data-auth-token, etc.
    if normalized_name.startswith("data-"):
        suffix = normalized_name[5:]

        if any(
            part in suffix
            for part in SENSITIVE_ATTRIBUTE_PARTS
        ):
            return True

    if normalized_name == "value":
        attrs_map = {
            attr_name.lower(): (attr_value or "")
            for attr_name, attr_value in attrs
        }

        input_type = attrs_map.get(
            "type",
            "",
        ).lower()

        field_name = attrs_map.get(
            "name",
            "",
        ).lower()

        field_id = attrs_map.get(
            "id",
            "",
        ).lower()

        placeholder = attrs_map.get(
            "placeholder",
            "",
        ).lower()

        if tag == "input" and input_type == "password":
            return True

        sensitive_context = (
            field_name,
            field_id,
            placeholder,
        )

        return any(
            any(
                token in context
                for token in SENSITIVE_ATTRIBUTE_PARTS
            )
            for context in sensitive_context
        )

    # URLs may contain credentials/tokens in query parameters.
    if normalized_name in {"href", "src"}:
        raw_attrs = {
            attr_name.lower(): (attr_value or "")
            for attr_name, attr_value in attrs
        }

        url = raw_attrs.get(normalized_name, "")

        return bool(
            SECRET_KV_RE.search(url)
            or BEARER_RE.search(url)
        )

    return False


def _clean_attribute_value(value: str) -> str:
    """Clean and sanitize an HTML attribute value."""
    value = str(value or "")

    # Null bytes have no legitimate value in locator metadata and can
    # interfere with downstream processing.
    value = value.replace("\x00", "")

    return _mask_sensitive_text(value)


def _escape_attribute(value: str) -> str:
    """Escape an attribute value for serialized HTML."""
    return html_lib.escape(
        value,
        quote=True,
    )


class _SanitizingHTMLParser(HTMLParser):
    """HTML parser that emits a compact, sanitized DOM representation."""

    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True,
        )

        self.parts: list[str] = []
        self.skip_depth = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _serialize_attrs(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> str:
        """Serialize allowed and sanitized attributes."""
        attr_parts: list[str] = []

        for name, value in attrs:
            name = (name or "").lower().strip()

            if not name:
                continue

            # Never pass event-handler attributes to the model.
            #
            # This also prevents accidental inclusion of executable
            # JavaScript such as onclick/onload/etc.
            if name.startswith("on"):
                continue

            # Keep explicit locator-related attributes and useful data-*.
            if (
                name not in ALLOWED_ATTRS
                and not name.startswith("data-")
            ):
                continue

            if value is None:
                attr_parts.append(name)
                continue

            if _attribute_is_sensitive(
                tag,
                attrs,
                name,
            ):
                attr_parts.append(
                    f'{name}="[REDACTED]"'
                )
                continue

            cleaned_value = _clean_attribute_value(
                value
            )

            attr_parts.append(
                f'{name}="{_escape_attribute(cleaned_value)}"'
            )

        if not attr_parts:
            return ""

        return " " + " ".join(attr_parts)

    def _append_start_tag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        self_closing: bool = False,
    ) -> None:
        """Append a sanitized start tag."""
        serialized_attrs = self._serialize_attrs(
            tag,
            attrs,
        )

        if self_closing:
            self.parts.append(
                f"<{tag}{serialized_attrs} />"
            )
        else:
            self.parts.append(
                f"<{tag}{serialized_attrs}>"
            )

    # ------------------------------------------------------------------
    # HTMLParser handlers
    # ------------------------------------------------------------------

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Handle an opening HTML tag."""
        tag = tag.lower()

        if tag in DROP_TAGS:
            self.skip_depth += 1
            return

        if self.skip_depth:
            return

        self._append_start_tag(
            tag,
            attrs,
        )

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        """Handle a closing HTML tag."""
        tag = tag.lower()

        if tag in DROP_TAGS:
            self.skip_depth = max(
                0,
                self.skip_depth - 1,
            )
            return

        if self.skip_depth:
            return

        if tag in VOID_TAGS:
            return

        self.parts.append(
            f"</{tag}>"
        )

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Handle a self-closing HTML tag."""
        tag = tag.lower()

        if tag in DROP_TAGS or self.skip_depth:
            return

        self._append_start_tag(
            tag,
            attrs,
            self_closing=True,
        )

    def handle_data(
        self,
        data: str,
    ) -> None:
        """Handle visible/textual DOM content."""
        if self.skip_depth:
            return

        cleaned = _mask_sensitive_text(
            data
        ).replace(
            "\x00",
            "",
        )

        if cleaned:
            self.parts.append(cleaned)

    def handle_comment(
        self,
        data: str,
    ) -> None:
        """Ignore HTML comments."""
        return

    def handle_decl(
        self,
        decl: str,
    ) -> None:
        """Ignore declarations such as DOCTYPE."""
        return

    def unknown_decl(
        self,
        data: str,
    ) -> None:
        """Ignore unknown declarations."""
        return


def compact_html(
    html: str,
    max_chars: int,
) -> str:
    """
    Sanitize and compact HTML before sending it to an AI provider.

    Args:
        html:
            Raw HTML obtained from Selenium/WebDriver.

        max_chars:
            Maximum number of characters returned.

    Returns:
        Sanitized, whitespace-compacted HTML.

    Raises:
        HtmlSanitizationError:
            If the input cannot be processed or max_chars is invalid.
    """
    if max_chars <= 0:
        raise HtmlSanitizationError(
            "max_chars must be positive"
        )

    if html is None:
        html = ""

    if not isinstance(html, str):
        html = str(html)

    try:
        parser = _SanitizingHTMLParser()

        parser.feed(html)
        parser.close()

        sanitized = "".join(
            parser.parts
        )

        # Compact whitespace without destroying attribute values.
        sanitized = re.sub(
            r"\s+",
            " ",
            sanitized,
        ).strip()

        if len(sanitized) > max_chars:
            sanitized = sanitized[:max_chars]

        return sanitized

    except Exception as exc:  # pragma: no cover - defensive
        raise HtmlSanitizationError(
            f"Failed to sanitize HTML: {exc}"
        ) from exc
