"""Core primitives for the self_healer package."""

from .candidate_validator import validate_candidate
from .config import SelfHealerConfig
from .exceptions import (
    HtmlSanitizationError,
    InvalidLocatorCandidate,
    LLMProviderError,
    LocatorResolutionError,
    SelfHealerError,
    SelfHealingFailed,
    StoreError,
)
from .healing_engine import HealingEngine
from .html_sanitizer import compact_html
from .models import HealingContext, HealingResult, LocatorCandidate, LocatorIdentity
from .sqlite_store import SelfHealerStore

__all__ = [
    "HealingContext",
    "HealingEngine",
    "HealingResult",
    "HtmlSanitizationError",
    "InvalidLocatorCandidate",
    "LLMProviderError",
    "LocatorCandidate",
    "LocatorIdentity",
    "LocatorResolutionError",
    "SelfHealerConfig",
    "SelfHealerError",
    "SelfHealerStore",
    "SelfHealingFailed",
    "StoreError",
    "compact_html",
    "validate_candidate",
]