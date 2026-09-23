"""Public API for the self_healer package."""

from .base import SelfHealer
from .core.config import SelfHealerConfig
from .core.exceptions import (
	HtmlSanitizationError,
	InvalidLocatorCandidate,
	LLMProviderError,
	LocatorResolutionError,
	SelfHealerError,
	SelfHealingFailed,
	StoreError,
)
from .core.models import HealingContext, HealingResult, LocatorCandidate, LocatorIdentity
from .providers.base import LocatorGenerator
from .providers.fake_provider import FakeLocatorGenerator
from .providers.openai_provider import OpenAILocatorGenerator
from .selenium_adapter.driver import HealableWebDriver
from .selenium_adapter.element import HealableWebElement

__all__ = [
	"FakeLocatorGenerator",
	"HealingContext",
	"HealingResult",
	"HealableWebDriver",
	"HealableWebElement",
	"HtmlSanitizationError",
	"InvalidLocatorCandidate",
	"LLMProviderError",
	"LocatorCandidate",
	"LocatorGenerator",
	"LocatorIdentity",
	"LocatorResolutionError",
	"OpenAILocatorGenerator",
	"SelfHealer",
	"SelfHealerConfig",
	"SelfHealerError",
	"SelfHealingFailed",
	"StoreError",
]
