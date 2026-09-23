"""
Wrapper around Selenium WebDriver with self-healing support.

The HealableWebDriver is responsible for:

1. Converting Selenium locators to internal LocatorCandidate objects.
2. Resolving normal Selenium locators against the live DOM.
3. Reusing previously successful locators through the healing engine.
4. Asking the healing engine for alternative locators when resolution fails.
5. Validating every healed locator against the live Selenium DOM.
6. Wrapping returned WebElements in HealableWebElement.
7. Preserving Selenium-compatible behaviour wherever possible.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from selenium.common.exceptions import (
    InvalidSelectorException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from ..core.candidate_validator import validate_candidate
from ..core.config import SelfHealerConfig
from ..core.exceptions import (
    InvalidLocatorCandidate,
    SelfHealingFailed,
)
from ..core.healing_engine import HealingEngine
from ..core.html_sanitizer import compact_html
from ..core.models import (
    HealingContext,
    LocatorCandidate,
    LocatorIdentity,
)
from ..core.sqlite_store import SelfHealerStore
from .locator_mapper import (
    candidate_to_by,
    map_by_to_candidate,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _auto_key(
    project_name: str,
    page_key: str,
    by: str,
    value: str,
) -> str:
    """
    Create a deterministic identity when no explicit key is supplied.

    The locator itself is included in the fallback key so two different
    selectors do not accidentally share the same healing identity.
    """
    payload = (
        f"{project_name}|{page_key}|{by}|{value}"
        .encode("utf-8", errors="ignore")
    )

    return hashlib.sha256(payload).hexdigest()[:16]


def _normalize_description(
    description: str | None,
) -> str:
    """Normalize an optional semantic element description."""
    return (description or "").strip()


def _unwrap_argument(value: Any) -> Any:
    """
    Convert healable elements into raw Selenium elements.

    This keeps execute_script() and execute_async_script() compatible
    with wrapped WebElements.

    Lists, tuples and dictionaries are recursively supported.
    """
    from .element import HealableWebElement

    if isinstance(value, HealableWebElement):
        return value.raw

    if isinstance(value, list):
        return [
            _unwrap_argument(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            _unwrap_argument(item)
            for item in value
        )

    if isinstance(value, dict):
        return {
            key: _unwrap_argument(item)
            for key, item in value.items()
        }

    return value


# ----------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------

class HealableWebDriver:
    """
    Selenium WebDriver wrapper with self-healing locator support.

    Only find_element() and find_elements() are intercepted.

    Everything else is delegated automatically to the underlying
    Selenium WebDriver through __getattr__().

    This means existing bot code can continue doing:

        driver.get(...)
        driver.refresh()
        driver.execute_cdp_cmd(...)
        driver.add_cookie(...)
        driver.maximize_window()
        driver.current_url
        driver.switch_to
        driver.file_detector

    without modifications.
    """

    def __init__(
        self,
        driver,
        config: SelfHealerConfig,
        locator_generator,
        store: SelfHealerStore | None = None,
    ) -> None:

        if driver is None:
            raise ValueError(
                "A Selenium WebDriver instance is required."
            )

        if config is None:
            raise ValueError(
                "SelfHealerConfig is required."
            )

        if locator_generator is None:
            raise ValueError(
                "locator_generator is required."
            )

        self._raw = driver
        self.config = config
        self.locator_generator = locator_generator

        self.store = store or SelfHealerStore(
            config.db_path,
            disable_after_failures=(
                config.disable_after_failures
            ),
        )

        self.engine = HealingEngine(
            self.store,
            locator_generator,
            config,
        )

        self._closed = False

    # ------------------------------------------------------------------
    # Selenium compatibility
    # ------------------------------------------------------------------

    @property
    def raw(self):
        """
        Return the underlying Selenium WebDriver.

        This is useful when an integration explicitly needs the real
        Selenium driver.
        """
        return self._raw

    @property
    def raw_driver(self):
        """Alias for raw, kept for integration convenience."""
        return self._raw

    def __getattr__(self, item: str):
        """
        Delegate unsupported WebDriver attributes to Selenium.

        This is critical for compatibility with the existing Automate
        class.
        """
        return getattr(self._raw, item)

    # ------------------------------------------------------------------
    # Identity / locator conversion
    # ------------------------------------------------------------------

    def _identity(
        self,
        key: str | None,
        page_key: str | None,
        by: str,
        value: str,
        description: str | None = None,
    ) -> LocatorIdentity:
        """Build a stable identity for an element."""

        semantic_hint = _normalize_description(
            description
        )

        element_key = (
            key
            or semantic_hint
            or _auto_key(
                self.config.project_name,
                page_key or "default",
                by,
                value,
            )
        )

        return LocatorIdentity(
            project_name=self.config.project_name,
            framework="selenium",
            page_key=page_key or "default",
            element_key=element_key,
        )

    def _to_original_candidate(
        self,
        by: str,
        value: str,
    ) -> LocatorCandidate:
        """Convert a Selenium locator into an internal candidate."""

        if not isinstance(value, str):
            raise InvalidLocatorCandidate(
                "Locator value must be a string."
            )

        if not value.strip():
            raise InvalidLocatorCandidate(
                "Locator value cannot be empty."
            )

        normalized_by = (
            (by or "")
            .strip()
            .lower()
        )

        if normalized_by in {
            "css",
            "css selector",
            "css_selector",
        }:
            candidate = LocatorCandidate(
                strategy="css",
                value=value,
                name="css",
            )

        elif normalized_by == "xpath":
            candidate = LocatorCandidate(
                strategy="xpath",
                value=value,
                name="xpath",
            )

        else:
            candidate = map_by_to_candidate(
                by,
                value,
            )

        return self._validate_candidate(
            candidate
        )

    def _validate_candidate(
        self,
        candidate: LocatorCandidate,
    ) -> LocatorCandidate:
        """Validate and normalize a locator candidate."""

        if candidate is None:
            raise InvalidLocatorCandidate(
                "Locator candidate cannot be None."
            )

        try:
            return validate_candidate(
                candidate
            )

        except InvalidLocatorCandidate:
            raise

        except Exception as exc:
            raise InvalidLocatorCandidate(
                f"Invalid locator candidate: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Live DOM probing
    # ------------------------------------------------------------------

    def _probe_one(
        self,
        candidate: LocatorCandidate,
    ):
        """Resolve exactly one element against the live DOM."""

        candidate = self._validate_candidate(
            candidate
        )

        strategy, value = candidate_to_by(
            candidate
        )

        return self._raw.find_element(
            strategy,
            value,
        )

    def _probe_many(
        self,
        candidate: LocatorCandidate,
    ):
        """Resolve zero or more elements against the live DOM."""

        candidate = self._validate_candidate(
            candidate
        )

        strategy, value = candidate_to_by(
            candidate
        )

        return self._raw.find_elements(
            strategy,
            value,
        )

    # ------------------------------------------------------------------
    # Healing context
    # ------------------------------------------------------------------

    def _build_context(
        self,
        identity: LocatorIdentity,
        by: str,
        value: str,
        action: str,
        error: str = "",
        description: str = "",
    ) -> HealingContext:
        """Build sanitized context for the healing engine."""

        candidate = self._to_original_candidate(
            by,
            value,
        )

        page_source = ""

        try:
            page_source = getattr(
                self._raw,
                "page_source",
                "",
            ) or ""
        except WebDriverException:
            logger.warning(
                "Could not retrieve Selenium page_source."
            )

        try:
            page_source = compact_html(
                page_source,
                self.config.max_html_chars,
            )
        except Exception as exc:
            logger.warning(
                "HTML sanitization failed: %s",
                exc,
            )
            page_source = ""

        current_url = ""

        try:
            current_url = getattr(
                self._raw,
                "current_url",
                "",
            ) or ""
        except WebDriverException:
            current_url = ""

        return HealingContext(
            identity=identity,
            url=current_url,
            original_strategy=candidate.strategy,
            original_value=candidate.value,
            html=page_source,
            action=action,
            error=(error or "").strip(),
            target_description=_normalize_description(
                description
            ),
        )

    # ------------------------------------------------------------------
    # Element wrapping
    # ------------------------------------------------------------------

    def _wrap_element(
        self,
        raw_element,
        identity: LocatorIdentity,
        original_locator: LocatorCandidate,
        current_locator: LocatorCandidate,
    ):
        """
        Wrap a Selenium WebElement with healing support.
        """
        from .element import HealableWebElement

        return HealableWebElement(
            owner=self,
            raw=raw_element,
            identity=identity,
            original_locator=original_locator,
            current_locator=current_locator,
            timeout=self.config.timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Candidate acceptance
    # ------------------------------------------------------------------

    def _accept_one(
        self,
        candidate: LocatorCandidate,
    ):
        """
        Validate and resolve a candidate against the live DOM.
        """

        candidate = self._validate_candidate(
            candidate
        )

        raw_element = self._probe_one(
            candidate
        )

        if raw_element is None:
            raise NoSuchElementException(
                "Candidate resolved to no element: "
                f"{candidate.strategy}="
                f"{candidate.value}"
            )

        return raw_element

    def _accept_many(
        self,
        candidate: LocatorCandidate,
    ):
        """
        Validate and resolve a multi-element candidate.
        """

        candidate = self._validate_candidate(
            candidate
        )

        return self._probe_many(
            candidate
        )

    # ------------------------------------------------------------------
    # Healing
    # ------------------------------------------------------------------

    def _heal_one(
        self,
        context: HealingContext,
        *,
        allow_ai: bool,
    ):
        """Delegate single-element healing to HealingEngine."""

        return self.engine.heal(
            context,
            self._probe_one,
            allow_saved=True,
            allow_ai=allow_ai,
        )

    def _heal_many(
        self,
        context: HealingContext,
        *,
        allow_ai: bool,
    ):
        """Delegate multi-element healing to HealingEngine."""

        return self.engine.heal(
            context,
            self._probe_many,
            allow_saved=True,
            allow_ai=allow_ai,
        )

    # ------------------------------------------------------------------
    # Single-element resolution
    # ------------------------------------------------------------------

    def _resolve_one(
        self,
        by: str,
        value: str,
        *,
        key: str | None = None,
        page_key: str | None = None,
        description: str = "",
        action: str = "find_element",
        allow_ai: bool | None = None,
        error: str = "",
    ):
        """
        Resolve one element, invoking self-healing when necessary.
        """

        identity = self._identity(
            key,
            page_key,
            by,
            value,
            description=description,
        )

        original_candidate = (
            self._to_original_candidate(
                by,
                value,
            )
        )

        if allow_ai is None:
            allow_ai = bool(
                self.config.allow_ai
            )

        # --------------------------------------------------------------
        # Healing disabled
        # --------------------------------------------------------------

        if not self.config.enabled:
            raw_element = self._accept_one(
                original_candidate
            )

            return (
                raw_element,
                identity,
                original_candidate,
                original_candidate,
            )

        # --------------------------------------------------------------
        # Fast path: original locator
        # --------------------------------------------------------------

        try:
            raw_element = self._accept_one(
                original_candidate
            )

        except InvalidLocatorCandidate:
            # Programming/configuration error.
            raise

        except (
            InvalidSelectorException,
            NoSuchElementException,
            StaleElementReferenceException,
            TimeoutException,
        ) as exc:

            failure_message = str(exc).strip()

            logger.warning(
                "Selenium locator failed: "
                "by=%s value=%s error=%s",
                by,
                value,
                type(exc).__name__,
            )

            context = self._build_context(
                identity,
                by,
                value,
                action,
                failure_message or error,
                description,
            )

            # ----------------------------------------------------------
            # Self-Healer
            # ----------------------------------------------------------

            try:
                result = self._heal_one(
                    context,
                    allow_ai=(
                        bool(allow_ai)
                        and bool(
                            self.config.heal_on_find
                        )
                    ),
                )

            except SelfHealingFailed as heal_exc:
                raise SelfHealingFailed(
                    f"Unable to heal locator for "
                    f"'{identity.element_key}': "
                    f"{heal_exc}"
                ) from heal_exc

            except WebDriverException:
                # Browser/session errors must propagate.
                raise

            if (
                result is None
                or not result.success
                or result.candidate is None
            ):
                raise SelfHealingFailed(
                    f"Healing returned no usable "
                    f"candidate for "
                    f"'{identity.element_key}'."
                )

            # ----------------------------------------------------------
            # Final validation
            # ----------------------------------------------------------

            healed_candidate = self._validate_candidate(
                result.candidate
            )

            try:
                healed_raw = self._accept_one(
                    healed_candidate
                )

            except (
                InvalidLocatorCandidate,
                InvalidSelectorException,
                NoSuchElementException,
                StaleElementReferenceException,
                TimeoutException,
            ) as heal_exc:

                raise SelfHealingFailed(
                    f"Healed locator failed final "
                    f"live DOM validation for "
                    f"'{identity.element_key}': "
                    f"{heal_exc}"
                ) from heal_exc

            return (
                healed_raw,
                identity,
                original_candidate,
                healed_candidate,
            )

        except WebDriverException:
            # Browser/session/network failures should propagate.
            raise

        # --------------------------------------------------------------
        # Original locator worked
        # --------------------------------------------------------------

        if raw_element is None:
            raise NoSuchElementException(
                f"No element found for "
                f"{by}={value}"
            )

        return (
            raw_element,
            identity,
            original_candidate,
            original_candidate,
        )

    # ------------------------------------------------------------------
    # Multiple-element resolution
    # ------------------------------------------------------------------

    def _resolve_many(
        self,
        by: str,
        value: str,
        *,
        key: str | None = None,
        page_key: str | None = None,
        description: str = "",
        action: str = "find_elements",
        allow_ai: bool | None = None,
        error: str = "",
    ):
        """
        Resolve multiple elements with Selenium-compatible semantics.
        """

        identity = self._identity(
            key,
            page_key,
            by,
            value,
            description=description,
        )

        original_candidate = (
            self._to_original_candidate(
                by,
                value,
            )
        )

        if allow_ai is None:
            allow_ai = bool(
                self.config.allow_ai
            )

        # --------------------------------------------------------------
        # Healing disabled
        # --------------------------------------------------------------

        if not self.config.enabled:
            raw_elements = self._accept_many(
                original_candidate
            )

            return (
                raw_elements,
                identity,
                original_candidate,
                original_candidate,
            )

        # --------------------------------------------------------------
        # Fast path
        # --------------------------------------------------------------

        try:
            raw_elements = self._accept_many(
                original_candidate
            )

        except InvalidLocatorCandidate:
            raise

        except (
            InvalidSelectorException,
            StaleElementReferenceException,
            TimeoutException,
        ) as exc:

            failure_message = str(exc).strip()

            logger.warning(
                "Selenium multi-element locator failed: "
                "by=%s value=%s error=%s",
                by,
                value,
                type(exc).__name__,
            )

            context = self._build_context(
                identity,
                by,
                value,
                action,
                failure_message or error,
                description,
            )

            try:
                result = self._heal_many(
                    context,
                    allow_ai=(
                        bool(allow_ai)
                        and bool(
                            self.config.heal_on_find
                        )
                    ),
                )

            except SelfHealingFailed:
                # Preserve Selenium-like behaviour for find_elements.
                return (
                    [],
                    identity,
                    original_candidate,
                    original_candidate,
                )

            except WebDriverException:
                raise

            if (
                result is None
                or not result.success
                or result.candidate is None
            ):
                return (
                    [],
                    identity,
                    original_candidate,
                    original_candidate,
                )

            healed_candidate = self._validate_candidate(
                result.candidate
            )

            try:
                healed_raw = self._accept_many(
                    healed_candidate
                )

            except (
                InvalidLocatorCandidate,
                InvalidSelectorException,
                StaleElementReferenceException,
                TimeoutException,
            ) as heal_exc:

                raise SelfHealingFailed(
                    f"Healed locator failed final "
                    f"live DOM validation for "
                    f"'{identity.element_key}': "
                    f"{heal_exc}"
                ) from heal_exc

            if not healed_raw:
                return (
                    [],
                    identity,
                    original_candidate,
                    healed_candidate,
                )

            return (
                healed_raw,
                identity,
                original_candidate,
                healed_candidate,
            )

        except WebDriverException:
            raise

        # --------------------------------------------------------------
        # Selenium find_elements() legitimately returned []
        # --------------------------------------------------------------

        if raw_elements:
            return (
                raw_elements,
                identity,
                original_candidate,
                original_candidate,
            )

        # Do not heal if healing-on-find is disabled.
        if not self.config.heal_on_find:
            return (
                [],
                identity,
                original_candidate,
                original_candidate,
            )

        # AI is disabled, but saved locators may still be useful.
        # Therefore allow the engine to try its saved-locator path.
        context = self._build_context(
            identity,
            by,
            value,
            action,
            error,
            description,
        )

        try:
            result = self._heal_many(
                context,
                allow_ai=bool(allow_ai),
            )

        except SelfHealingFailed:
            # find_elements must preserve [] semantics.
            return (
                [],
                identity,
                original_candidate,
                original_candidate,
            )

        except WebDriverException:
            raise

        if (
            result is None
            or not result.success
            or result.candidate is None
        ):
            return (
                [],
                identity,
                original_candidate,
                original_candidate,
            )

        healed_candidate = self._validate_candidate(
            result.candidate
        )

        try:
            healed_raw = self._accept_many(
                healed_candidate
            )

        except (
            InvalidLocatorCandidate,
            InvalidSelectorException,
            StaleElementReferenceException,
            TimeoutException,
        ) as exc:

            raise SelfHealingFailed(
                f"Healed locator failed final "
                f"live DOM validation for "
                f"'{identity.element_key}': "
                f"{exc}"
            ) from exc

        if not healed_raw:
            return (
                [],
                identity,
                original_candidate,
                healed_candidate,
            )

        return (
            healed_raw,
            identity,
            original_candidate,
            healed_candidate,
        )

    # ------------------------------------------------------------------
    # Public Selenium-compatible API
    # ------------------------------------------------------------------

    def find_element(
        self,
        by: str,
        value: str,
        key: str | None = None,
        page_key: str | None = None,
        description: str = "",
    ):
        """
        Find one element and return a healable wrapper.

        Existing Selenium code remains compatible:

            driver.find_element(By.XPATH, xpath)
        """

        (
            raw_element,
            identity,
            original_locator,
            current_locator,
        ) = self._resolve_one(
            by,
            value,
            key=key,
            page_key=page_key,
            description=description,
            action="find_element",
        )

        return self._wrap_element(
            raw_element,
            identity,
            original_locator,
            current_locator,
        )

    def find_elements(
        self,
        by: str,
        value: str,
        key: str | None = None,
        page_key: str | None = None,
        description: str = "",
    ):
        """
        Find multiple elements and return healable wrappers.
        """

        (
            raw_elements,
            identity,
            original_locator,
            current_locator,
        ) = self._resolve_many(
            by,
            value,
            key=key,
            page_key=page_key,
            description=description,
            action="find_elements",
        )

        return [
            self._wrap_element(
                raw_element,
                identity,
                original_locator,
                current_locator,
            )
            for raw_element in raw_elements
        ]

    # ------------------------------------------------------------------
    # JavaScript
    # ------------------------------------------------------------------

    def execute_script(
        self,
        script: str,
        *args: Any,
    ):
        """
        Execute JavaScript while automatically unwrapping
        HealableWebElement instances.
        """

        return self._raw.execute_script(
            script,
            *[
                _unwrap_argument(argument)
                for argument in args
            ],
        )

    def execute_async_script(
        self,
        script: str,
        *args: Any,
    ):
        """
        Execute asynchronous JavaScript while automatically unwrapping
        HealableWebElement instances.
        """

        return self._raw.execute_async_script(
            script,
            *[
                _unwrap_argument(argument)
                for argument in args
            ],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """
        Close the current browser window.

        The healing store remains available because the Selenium session
        itself may still contain other windows.
        """

        if self._closed:
            return

        self._raw.close()

    def quit(self) -> None:
        """
        Quit Selenium and close the Self-Healer store.
        """

        if self._closed:
            return

        try:
            self._raw.quit()

        finally:
            self._closed = True

            if self.store is not None:
                try:
                    self.store.close()
                except Exception:
                    logger.debug(
                        "Error closing Self-Healer store.",
                        exc_info=True,
                    )

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            "<HealableWebDriver "
            f"project={self.config.project_name!r} "
            f"enabled={self.config.enabled}>"
        )
