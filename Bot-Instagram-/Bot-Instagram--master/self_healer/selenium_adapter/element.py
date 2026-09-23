"""Wrapper around Selenium WebElement with self-healing on actions.

This module provides a thin wrapper around Selenium's WebElement that
automatically retries failed interactions through the Self-Healer engine.

The wrapper delegates locator resolution and validation to the owner/driver
adapter. AI-generated locators are never trusted directly: the owner must
validate and probe them against the live Selenium DOM before returning them.
"""

from __future__ import annotations

from typing import Any, Callable

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    InvalidSelectorException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)

from ..core.exceptions import SelfHealingFailed
from ..core.models import LocatorCandidate, LocatorIdentity


# Exceptions for which locator re-resolution can reasonably help.
#
# Do NOT include generic WebDriverException here. It can represent browser
# crashes, disconnected sessions, invalid sessions, transport failures, etc.
RECOVERABLE_EXCEPTIONS = (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    InvalidSelectorException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)


class HealableWebElement:
    """Selenium WebElement wrapper with optional self-healing.

    The wrapper stores:

    - the original locator requested by the application;
    - the locator currently known to work;
    - the underlying Selenium WebElement.

    If an interaction fails because the element became stale, disappeared,
    became temporarily non-interactable, etc., the owner is asked to resolve
    the original locator again through the self-healing pipeline.
    """

    def __init__(
        self,
        owner,
        raw,
        identity: LocatorIdentity,
        original_locator: LocatorCandidate,
        current_locator: LocatorCandidate,
        timeout: int,
    ) -> None:
        if raw is None:
            raise ValueError("HealableWebElement requires a raw WebElement.")

        if owner is None:
            raise ValueError("HealableWebElement requires an owner.")

        self._owner = owner
        self._raw = raw

        self.identity = identity

        # Locator originally supplied by the application.
        self.original_locator = original_locator

        # Locator that produced the currently active raw element.
        self.current_locator = current_locator

        self.timeout = timeout

        # Extension point for adapters/integrations.
        self.metadata: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Raw Selenium access
    # ------------------------------------------------------------------

    @property
    def raw(self):
        """Return the underlying Selenium WebElement."""
        return self._raw

    def unwrap(self):
        """Return the underlying Selenium WebElement.

        Useful for third-party Selenium APIs that explicitly require a
        native WebElement instance.
        """
        return self._raw

    def __getattr__(self, item: str):
        """Delegate unsupported attributes and methods to WebElement.

        This is important for Selenium compatibility because WebElement has
        many APIs that are not worth duplicating in this wrapper, such as:

        - tag_name
        - id
        - location
        - size
        - rect
        - value_of_css_property
        - screenshot
        - aria_role
        - accessible_name
        - etc.
        """
        return getattr(self._raw, item)

    def __repr__(self) -> str:
        return (
            f"<HealableWebElement "
            f"element_key={self.identity.element_key!r} "
            f"locator={self.current_locator!r}>"
        )

    # ------------------------------------------------------------------
    # Internal healing
    # ------------------------------------------------------------------

    def _refresh(self, action: str, error: Exception) -> None:
        """Resolve the element again through the owner's healing pipeline.

        The owner is responsible for:

        1. Reading the current DOM.
        2. Trying saved locators.
        3. Trying the original locator.
        4. Asking the AI provider for candidates when enabled.
        5. Validating candidates.
        6. Probing candidates against the live Selenium driver.
        7. Returning only a locator that actually resolves.
        """
        try:
            (
                raw_element,
                _identity,
                _original_candidate,
                current_candidate,
            ) = self._owner._resolve_one(
                self.original_locator.strategy,
                self.original_locator.value,
                key=self.identity.element_key,
                page_key=self.identity.page_key,
                description=self.identity.element_key,
                action=action,
                error=str(error),
                allow_ai=self._owner.config.heal_on_action,
            )

        except Exception as exc:
            raise SelfHealingFailed(
                f"Self-healing failed while resolving "
                f"'{self.identity.element_key}' during '{action}': {exc}"
            ) from exc

        if raw_element is None:
            raise SelfHealingFailed(
                f"Self-healing returned no element for "
                f"'{self.identity.element_key}' during '{action}'."
            )

        if current_candidate is None:
            raise SelfHealingFailed(
                f"Self-healing returned no locator candidate for "
                f"'{self.identity.element_key}' during '{action}'."
            )

        self._raw = raw_element
        self.current_locator = current_candidate

    def _call_with_healing(
        self,
        action: str,
        callback: Callable[[], Any],
    ) -> Any:
        """Execute an operation and retry once after locator healing.

        Flow:

            operation
                ↓
            recoverable Selenium error
                ↓
            resolve original locator
                ↓
            validate/probe/heal
                ↓
            update raw WebElement
                ↓
            retry operation once

        The callback is intentionally executed only twice at most.
        """

        try:
            return callback()

        except RECOVERABLE_EXCEPTIONS as exc:
            if not self._owner.config.heal_on_action:
                raise

            self._refresh(action, exc)

            try:
                return callback()

            except RECOVERABLE_EXCEPTIONS as retry_exc:
                raise SelfHealingFailed(
                    f"Self-healing retry failed for "
                    f"'{self.identity.element_key}' during '{action}': "
                    f"{retry_exc}"
                ) from retry_exc

    # ------------------------------------------------------------------
    # Common WebElement actions
    # ------------------------------------------------------------------

    def click(self):
        """Click the element, healing once if necessary."""
        return self._call_with_healing(
            "click",
            self._raw.click,
        )

    def send_keys(self, *value: Any):
        """Send keyboard input to the element."""
        return self._call_with_healing(
            "send_keys",
            lambda: self._raw.send_keys(*value),
        )

    def clear(self):
        """Clear the element's current value."""
        return self._call_with_healing(
            "clear",
            self._raw.clear,
        )

    def submit(self):
        """Submit the element/form."""
        return self._call_with_healing(
            "submit",
            self._raw.submit,
        )

    # ------------------------------------------------------------------
    # Element information
    # ------------------------------------------------------------------

    def get_attribute(self, name: str):
        """Return a DOM attribute."""
        return self._call_with_healing(
            "get_attribute",
            lambda: self._raw.get_attribute(name),
        )

    def get_dom_attribute(self, name: str):
        """Return a DOM attribute using Selenium's DOM-attribute API."""
        return self._call_with_healing(
            "get_dom_attribute",
            lambda: self._raw.get_dom_attribute(name),
        )

    def get_property(self, name: str):
        """Return a JavaScript property exposed by Selenium."""
        return self._call_with_healing(
            "get_property",
            lambda: self._raw.get_property(name),
        )

    def is_displayed(self):
        """Return whether the element is displayed."""
        return self._call_with_healing(
            "is_displayed",
            self._raw.is_displayed,
        )

    def is_enabled(self):
        """Return whether the element is enabled."""
        return self._call_with_healing(
            "is_enabled",
            self._raw.is_enabled,
        )

    def is_selected(self):
        """Return whether the element is selected."""
        return self._call_with_healing(
            "is_selected",
            self._raw.is_selected,
        )

    @property
    def text(self):
        """Return the element's visible text."""
        return self._call_with_healing(
            "text",
            lambda: self._raw.text,
        )

    # ------------------------------------------------------------------
    # Nested element lookup
    # ------------------------------------------------------------------

    def find_element(
        self,
        by: str,
        value: str,
        key: str | None = None,
        page_key: str | None = None,
        description: str = "",
    ):
        """Find and wrap one nested element.

        Nested lookup is routed through the same healing pipeline as a
        top-level driver lookup.
        """
        element_key = key or self.identity.element_key
        resolved_page_key = page_key or self.identity.page_key
        resolved_description = description or element_key

        (
            raw_element,
            identity,
            original_candidate,
            current_candidate,
        ) = self._owner._resolve_one(
            by,
            value,
            key=element_key,
            page_key=resolved_page_key,
            description=resolved_description,
            action="nested_find_element",
        )

        return HealableWebElement(
            owner=self._owner,
            raw=raw_element,
            identity=identity,
            original_locator=original_candidate,
            current_locator=current_candidate,
            timeout=self.timeout,
        )

    def find_elements(
        self,
        by: str,
        value: str,
        key: str | None = None,
        page_key: str | None = None,
        description: str = "",
    ):
        """Find and wrap multiple nested elements."""
        element_key = key or self.identity.element_key
        resolved_page_key = page_key or self.identity.page_key
        resolved_description = description or element_key

        (
            raw_elements,
            identity,
            original_candidate,
            current_candidate,
        ) = self._owner._resolve_many(
            by,
            value,
            key=element_key,
            page_key=resolved_page_key,
            description=resolved_description,
            action="nested_find_elements",
        )

        return [
            HealableWebElement(
                owner=self._owner,
                raw=raw_element,
                identity=identity,
                original_locator=original_candidate,
                current_locator=current_candidate,
                timeout=self.timeout,
            )
            for raw_element in raw_elements
        ]
