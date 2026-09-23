"""Logging helpers for self_healer events.

The telemetry layer intentionally stays lightweight. It provides a single
structured-ish logging entry point that can be used by the healing engine,
Selenium adapter, persistence layer, and API without coupling those modules
to a specific logging backend.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any


logger = logging.getLogger("self_healer")


_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
}


def _is_sensitive_key(key: object) -> bool:
    """Return True when a field name looks sensitive."""
    normalized = str(key).strip().lower().replace("-", "_")

    if normalized in _SENSITIVE_KEYS:
        return True

    return any(
        part in normalized
        for part in (
            "api_key",
            "access_token",
            "refresh_token",
            "authorization",
            "password",
            "secret",
        )
    )


def _sanitize_value(key: object, value: Any) -> Any:
    """Remove or mask sensitive telemetry values."""
    if _is_sensitive_key(key):
        return "[REDACTED]"

    if isinstance(value, Mapping):
        return {
            str(nested_key): _sanitize_value(nested_key, nested_value)
            for nested_key, nested_value in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _sanitize_value(key, item)
            for item in value
        ]

    if isinstance(value, set):
        return [
            _sanitize_value(key, item)
            for item in value
        ]

    return value


def _sanitize_details(details: Mapping[str, object]) -> dict[str, object]:
    """Return telemetry details with sensitive fields redacted."""
    return {
        str(key): _sanitize_value(key, value)
        for key, value in details.items()
    }


def log_event(
    event: str,
    *,
    level: int = logging.INFO,
    **details: object,
) -> None:
    """Log a self_healer event.

    Parameters
    ----------
    event:
        Short machine-readable event name, for example
        ``"healing_started"`` or ``"candidate_validated"``.

    level:
        Standard Python logging level. Defaults to ``logging.INFO``.

    details:
        Optional structured event metadata. Sensitive fields such as API keys,
        tokens, passwords, and authorization values are automatically
        redacted.
    """
    event_name = str(event).strip() or "unknown_event"

    if details:
        safe_details = _sanitize_details(details)
        logger.log(level, "%s %s", event_name, safe_details)
    else:
        logger.log(level, "%s", event_name)


def log_debug(event: str, **details: object) -> None:
    """Log a debug-level self_healer event."""
    log_event(event, level=logging.DEBUG, **details)


def log_warning(event: str, **details: object) -> None:
    """Log a warning-level self_healer event."""
    log_event(event, level=logging.WARNING, **details)


def log_error(event: str, **details: object) -> None:
    """Log an error-level self_healer event."""
    log_event(event, level=logging.ERROR, **details)
