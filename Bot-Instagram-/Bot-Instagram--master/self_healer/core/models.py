"""Data models for the Selenium/web locator healing system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class LocatorCandidate:
    """A locator proposed by the application or the healing engine.

    A candidate represents a Selenium-compatible locator after conversion
    to the internal strategy/value format.

    Supported strategies are validated separately by
    ``candidate_validator.py``. This model only performs safe normalization.
    """

    strategy: str
    value: str
    name: str = ""
    confidence: float = 0.0
    reason: str = ""

    def __post_init__(self) -> None:
        """Normalize candidate fields."""
        if self.strategy is None:
            self.strategy = ""
        else:
            self.strategy = str(self.strategy).strip().lower()

        if self.value is None:
            self.value = ""
        else:
            self.value = str(self.value).strip()

        if self.name is None:
            self.name = ""
        else:
            self.name = str(self.name).strip()

        if self.reason is None:
            self.reason = ""
        else:
            self.reason = str(self.reason).strip()

        # Confidence is metadata supplied by the locator generator.
        # Clamp it to a predictable range instead of allowing invalid
        # values such as NaN, negative values or values above 1.
        try:
            self.confidence = float(self.confidence)
        except (TypeError, ValueError):
            self.confidence = 0.0

        if self.confidence < 0.0:
            self.confidence = 0.0
        elif self.confidence > 1.0:
            self.confidence = 1.0


@dataclass(slots=True)
class LocatorIdentity:
    """Stable identity of a locator target.

    The identity is used by the persistent store to associate learned
    locators with a project/page/element combination.
    """

    project_name: str
    framework: str = "selenium"
    page_key: str = "default"
    element_key: str = ""

    def __post_init__(self) -> None:
        """Normalize identity fields."""
        if self.project_name is None:
            self.project_name = ""
        else:
            self.project_name = str(self.project_name).strip()

        if self.framework is None:
            self.framework = "selenium"
        else:
            self.framework = (
                str(self.framework).strip().lower()
                or "selenium"
            )

        if self.page_key is None:
            self.page_key = "default"
        else:
            self.page_key = (
                str(self.page_key).strip()
                or "default"
            )

        if self.element_key is None:
            self.element_key = ""
        else:
            self.element_key = str(self.element_key).strip()


@dataclass(slots=True)
class HealingContext:
    """Context provided to the healing engine/LLM.

    ``html`` should already be sanitized and size-limited before constructing
    this object. The model does not perform HTML sanitization itself because
    that belongs to the HTML preprocessing layer.
    """

    identity: LocatorIdentity
    url: str
    original_strategy: str
    original_value: str
    html: str
    action: str = "find_element"
    error: str = ""
    target_description: str = ""

    def __post_init__(self) -> None:
        """Normalize context strings without altering HTML content."""
        if self.url is None:
            self.url = ""
        else:
            self.url = str(self.url).strip()

        if self.original_strategy is None:
            self.original_strategy = ""
        else:
            self.original_strategy = (
                str(self.original_strategy)
                .strip()
                .lower()
            )

        if self.original_value is None:
            self.original_value = ""
        else:
            self.original_value = str(self.original_value).strip()

        # HTML should not be aggressively stripped or otherwise transformed
        # here. It has already passed through compact_html()/sanitization.
        if self.html is None:
            self.html = ""
        elif not isinstance(self.html, str):
            self.html = str(self.html)

        if self.action is None:
            self.action = "find_element"
        else:
            self.action = (
                str(self.action).strip()
                or "find_element"
            )

        if self.error is None:
            self.error = ""
        else:
            self.error = str(self.error).strip()

        if self.target_description is None:
            self.target_description = ""
        else:
            self.target_description = str(
                self.target_description
            ).strip()


@dataclass(slots=True)
class HealingResult:
    """Result of a locator healing attempt."""

    success: bool
    candidate: LocatorCandidate | None = None
    error: str = ""
    source: str = ""
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        """Normalize result metadata."""
        self.success = bool(self.success)

        if self.error is None:
            self.error = ""
        else:
            self.error = str(self.error).strip()

        if self.source is None:
            self.source = ""
        else:
            self.source = str(self.source).strip()

        # If a result is marked unsuccessful, keeping a candidate is usually
        # misleading. Do not silently discard it, though, because callers
        # may use the candidate for diagnostics. Therefore we only normalize
        # the value here.
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)

