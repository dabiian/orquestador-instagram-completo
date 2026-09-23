"""Custom exceptions for self_healer."""

from __future__ import annotations


class SelfHealerError(Exception):
    """Base exception for self_healer failures."""


class SelfHealingFailed(SelfHealerError):
    """Raised when no locator candidate can resolve the element."""


class InvalidLocatorCandidate(SelfHealerError):
    """Raised when a candidate locator is malformed or unsupported."""


class LLMProviderError(SelfHealerError):
    """Raised when an LLM provider cannot generate candidates."""


class StoreError(SelfHealerError):
    """Raised when the SQLite store fails."""


class HtmlSanitizationError(SelfHealerError):
    """Raised when HTML cannot be sanitized."""


class LocatorResolutionError(SelfHealerError):
    """Raised when a locator cannot be translated or probed."""

