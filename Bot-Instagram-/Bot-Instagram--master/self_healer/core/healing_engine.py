"""Orchestration of the web/Selenium locator healing flow.

The HealingEngine coordinates the complete self-healing lifecycle:

    original locator
          ↓
    saved locator
          ↓
    AI-generated candidates
          ↓
    local candidate validation
          ↓
    live Selenium DOM probing
          ↓
    successful candidate
          ↓
    persistent locator storage

The engine never trusts an AI-generated locator merely because it is
syntactically valid. A candidate is considered successful only when the
provided probe function confirms that it resolves against the current DOM.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from .candidate_validator import validate_candidate
from .config import SelfHealerConfig
from .exceptions import (
    InvalidLocatorCandidate,
    LLMProviderError,
    SelfHealingFailed,
)
from .models import HealingContext, HealingResult, LocatorCandidate
from .telemetry import log_event


logger = logging.getLogger(__name__)


class HealingEngine:
    """Coordinate locator recovery and validation."""

    def __init__(
        self,
        store,
        locator_generator,
        config: SelfHealerConfig,
    ) -> None:
        if config is None:
            raise ValueError("SelfHealerConfig is required.")

        self.store = store
        self.locator_generator = locator_generator
        self.config = config

    # ================================================================
    # Candidate normalization
    # ================================================================

    def _normalize_candidates(
        self,
        candidates: Iterable[LocatorCandidate] | None,
    ) -> list[LocatorCandidate]:
        """Validate, normalize and deduplicate candidates."""

        if candidates is None:
            return []

        max_candidates = max(
            0,
            int(self.config.max_ai_candidates),
        )

        if max_candidates == 0:
            return []

        normalized: list[LocatorCandidate] = []
        seen: set[tuple[str, str]] = set()

        for candidate in candidates:
            if candidate is None:
                continue

            try:
                validated = validate_candidate(candidate)

            except InvalidLocatorCandidate as exc:
                logger.debug(
                    "Rejected invalid locator candidate: %s",
                    exc,
                )

                log_event(
                    "candidate_rejected",
                    strategy=getattr(candidate, "strategy", None),
                    candidate=getattr(candidate, "value", None),
                    error=str(exc),
                )

                continue

            except Exception as exc:
                logger.exception(
                    "Unexpected candidate validation failure."
                )

                log_event(
                    "candidate_validation_error",
                    strategy=getattr(candidate, "strategy", None),
                    candidate=getattr(candidate, "value", None),
                    error=str(exc),
                )

                continue

            strategy = validated.strategy.strip().lower()
            value = validated.value.strip()

            key = (strategy, value)

            if key in seen:
                continue

            seen.add(key)
            normalized.append(validated)

            if len(normalized) >= max_candidates:
                break

        return normalized

    # ================================================================
    # Probe helpers
    # ================================================================

    @staticmethod
    def _probe_succeeded(resolved: object) -> bool:
        """Determine whether a probe produced a usable result."""

        if resolved is None:
            return False

        if isinstance(
            resolved,
            (
                list,
                tuple,
                set,
                frozenset,
            ),
        ):
            return len(resolved) > 0

        return True

    def _probe_candidate(
        self,
        probe: Callable[
            [LocatorCandidate],
            object | None,
        ],
        candidate: LocatorCandidate,
    ) -> tuple[bool, str]:
        """Validate and probe one candidate."""

        if candidate is None:
            return False, "candidate is None"

        try:
            validated = validate_candidate(candidate)

        except InvalidLocatorCandidate as exc:
            return (
                False,
                f"invalid locator candidate: {exc}",
            )

        except Exception as exc:
            logger.exception(
                "Unexpected locator validation failure."
            )

            return (
                False,
                f"candidate validation failed: {exc}",
            )

        try:
            resolved = probe(validated)

        except Exception as exc:
            message = str(exc).strip()

            if not message:
                message = exc.__class__.__name__

            logger.debug(
                "Locator probe failed for %s=%r: %s",
                validated.strategy,
                validated.value,
                message,
            )

            return False, message

        if not self._probe_succeeded(resolved):
            return False, "candidate did not resolve"

        return True, ""

    # ================================================================
    # Persistence helpers
    # ================================================================

    def _save_success(
        self,
        context: HealingContext,
        candidate: LocatorCandidate,
    ) -> None:
        """Persist a successful locator without breaking healing."""

        if self.store is None:
            return

        try:
            self.store.save_success(
                context,
                candidate,
            )

        except Exception as exc:
            logger.exception(
                "Failed to persist successful locator."
            )

            log_event(
                "locator_persistence_failed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                candidate=candidate.value,
                strategy=candidate.strategy,
                error=str(exc),
            )

    def _save_failure(
        self,
        context: HealingContext,
        candidate: LocatorCandidate,
        error: str,
    ) -> None:
        """Persist a failed locator without breaking healing."""

        if self.store is None:
            return

        try:
            save_failure = getattr(
                self.store,
                "save_failure",
                None,
            )

            if callable(save_failure):
                save_failure(
                    context,
                    candidate,
                    error,
                )
                return

            mark_failure = getattr(
                self.store,
                "mark_locator_failure",
                None,
            )

            if callable(mark_failure):
                mark_failure(
                    context.identity,
                    candidate,
                    error,
                )

        except Exception as exc:
            logger.exception(
                "Failed to persist locator failure."
            )

            log_event(
                "locator_failure_persistence_failed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                candidate=candidate.value,
                strategy=candidate.strategy,
                error=str(exc),
            )

    # ================================================================
    # Saved locator
    # ================================================================

    def _try_saved_locator(
        self,
        context: HealingContext,
        probe: Callable[
            [LocatorCandidate],
            object | None,
        ],
    ) -> HealingResult | None:
        """
        Try all previously learned locators in priority order.

        Resolution order:

            saved locator #1
                ↓ fail
            saved locator #2
                ↓ fail
            saved locator #3
                ↓ fail
            ...
                ↓ all fail
            return None so the caller can continue to AI healing.

        Important:
            - Only enabled locators are candidates for reuse.
            - The database already orders locators by success/confidence.
            - The first locator that resolves wins.
            - AI is NOT called here.
            - A successful saved locator is reinforced in the database.
        """

        if self.store is None:
            return None

        # ------------------------------------------------------------
        # Retrieve ALL saved locators
        # ------------------------------------------------------------

        try:
            rows = self.store.list_locators(
                context.identity
            )

        except Exception as exc:
            logger.exception(
                "Failed to retrieve saved locators for %s.",
                context.identity.element_key,
            )

            log_event(
                "saved_locator_lookup_failed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                error=str(exc),
            )

            return None

        if not rows:
            logger.debug(
                "No saved locators found for %s.",
                context.identity.element_key,
            )

            return None

        # ------------------------------------------------------------
        # Try every saved locator in database priority order
        # ------------------------------------------------------------

        candidate_index = 0

        for row in rows:

            # Disabled locators must never be reused.
            if not bool(row.get("enabled", 1)):
                continue

            try:
                saved = LocatorCandidate(
                    strategy=row["strategy"],
                    value=row["value"],
                    name=row.get("name", ""),
                    confidence=float(
                        row.get("confidence", 0.0)
                    ),
                    reason=row.get("reason", ""),
                )

                saved = validate_candidate(saved)

            except Exception as exc:
                logger.warning(
                    "Saved locator is invalid and will be ignored: %s",
                    exc,
                )

                log_event(
                    "saved_locator_invalid",
                    identity=context.identity.element_key,
                    page_key=context.identity.page_key,
                    error=str(exc),
                )

                continue

            candidate_index += 1

            logger.debug(
                "[self-healer] probando locator guardado #%s: %s=%s",
                candidate_index, saved.strategy, saved.value,
            )

            logger.info(
                "Trying saved locator #%s for %s: %s=%s",
                candidate_index,
                context.identity.element_key,
                saved.strategy,
                saved.value,
            )

            log_event(
                "locator_saved_used",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                candidate=saved.value,
                strategy=saved.strategy,
                candidate_index=candidate_index,
            )

            # --------------------------------------------------------
            # Probe saved locator
            # --------------------------------------------------------

            success, error = self._probe_candidate(
                probe,
                saved,
            )

            # --------------------------------------------------------
            # SUCCESS
            # --------------------------------------------------------

            if success:

                logger.info("[self-healer] locator guardado #%s funcionó", candidate_index)

                self._save_success(
                    context,
                    saved,
                )

                log_event(
                    "saved_locator_success",
                    identity=context.identity.element_key,
                    page_key=context.identity.page_key,
                    candidate=saved.value,
                    strategy=saved.strategy,
                    candidate_index=candidate_index,
                )

                return HealingResult(
                    success=True,
                    candidate=saved,
                    source="saved_locator",
                )

            # --------------------------------------------------------
            # FAILURE
            # --------------------------------------------------------

            logger.debug("[self-healer] locator guardado #%s falló", candidate_index)

            self._mark_saved_failure(
                context,
                saved,
                error,
            )

            log_event(
                "saved_locator_failed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                candidate=saved.value,
                strategy=saved.strategy,
                candidate_index=candidate_index,
                error=error,
            )

        # ------------------------------------------------------------
        # ALL SAVED LOCATORS FAILED
        # ------------------------------------------------------------

        if candidate_index > 0:
            logger.debug("[self-healer] todos los locators guardados (%s) fallaron", candidate_index)

        return None
    def _mark_saved_failure(
        self,
        context: HealingContext,
        candidate: LocatorCandidate,
        error: str,
    ) -> None:
        """Record a saved-locator failure once."""

        if self.store is None:
            return

        try:
            mark_failure = getattr(
                self.store,
                "mark_locator_failure",
                None,
            )

            if callable(mark_failure):
                mark_failure(
                    context.identity,
                    candidate,
                    error,
                )
                return

            save_failure = getattr(
                self.store,
                "save_failure",
                None,
            )

            if callable(save_failure):
                save_failure(
                    context,
                    candidate,
                    error,
                )

        except Exception as exc:
            logger.exception(
                "Failed to record saved locator failure."
            )

            log_event(
                "saved_locator_failure_persistence_failed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                candidate=candidate.value,
                strategy=candidate.strategy,
                error=str(exc),
            )

    # ================================================================
    # Original locator
    # ================================================================

    def _try_original_locator(
        self,
        context: HealingContext,
        probe: Callable[
            [LocatorCandidate],
            object | None,
        ],
    ) -> HealingResult | None:
        """Try the original locator from the healing context."""

        if not context.original_strategy:
            return None

        if not context.original_value:
            return None

        original = LocatorCandidate(
            strategy=context.original_strategy,
            value=context.original_value,
            name=context.identity.element_key,
        )

        success, error = self._probe_candidate(
            probe,
            original,
        )

        if success:
            self._save_success(
                context,
                original,
            )

            log_event(
                "original_locator_used",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                candidate=original.value,
                strategy=original.strategy,
            )

            return HealingResult(
                success=True,
                candidate=original,
                source="original_locator",
            )

        # The original locator is not a learned candidate. We record
        # the failure as an event/locator observation, but do not make
        # it compete with future healed candidates unnecessarily.
        self._save_failure(
            context,
            original,
            error,
        )

        log_event(
            "original_locator_failed",
            identity=context.identity.element_key,
            page_key=context.identity.page_key,
            candidate=original.value,
            strategy=original.strategy,
            error=error,
        )

        return None

    # ================================================================
    # AI candidate generation
    # ================================================================

    def _generate_ai_candidates(
        self,
        context: HealingContext,
    ) -> list[LocatorCandidate]:
        """Generate and locally validate AI locator candidates."""

        if not self.config.allow_ai:
            return []

        if self.locator_generator is None:
            if self.config.fail_if_ai_unavailable:
                raise LLMProviderError(
                    "AI provider is unavailable."
                )

            return []

        log_event(
            "ai_requested",
            identity=context.identity.element_key,
            page_key=context.identity.page_key,
        )

        try:
            generated = self.locator_generator.generate(
                context
            )

        except Exception as exc:
            logger.exception(
                "Locator generator failed for %s.",
                context.identity.element_key,
            )

            log_event(
                "ai_generation_failed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                error=str(exc),
            )

            if self.config.fail_if_ai_unavailable:
                raise LLMProviderError(
                    f"AI locator generation failed: {exc}"
                ) from exc

            raise SelfHealingFailed(
                f"AI locator generation failed: {exc}"
            ) from exc

        if generated is None:
            return []

        # Providers normally return an iterable of candidates.
        # A single LocatorCandidate is also accepted defensively.
        if isinstance(
            generated,
            LocatorCandidate,
        ):
            generated = [generated]

        try:
            candidates = self._normalize_candidates(
                generated
            )

        except TypeError as exc:
            logger.exception(
                "AI provider returned an invalid candidate collection."
            )

            raise SelfHealingFailed(
                f"Invalid AI candidate collection: {exc}"
            ) from exc

        log_event(
            "ai_candidates_generated",
            identity=context.identity.element_key,
            page_key=context.identity.page_key,
            count=len(candidates),
        )

        return candidates

    # ================================================================
    # Main healing flow
    # ================================================================

    def heal(
        self,
        context: HealingContext,
        probe: Callable[
            [LocatorCandidate],
            object | None,
        ],
        *,
        allow_saved: bool = True,
        allow_ai: bool = True,
    ) -> HealingResult:
        """Attempt to heal a locator.

        Resolution order:

        1. Saved locator, when preferred.
        2. Original locator.
        3. Saved locator, when not preferred.
        4. AI-generated candidates.

        Every candidate is:

        1. normalized
        2. syntactically validated
        3. probed against the live Selenium DOM
        4. persisted only after successful resolution
        """
        if context is None:
            raise ValueError(
                "HealingContext is required."
            )

        if not callable(probe):
            raise TypeError(
                "probe must be a callable."
            )

        log_event(
            "healing_started",
            identity=context.identity.element_key,
            page_key=context.identity.page_key,
            action=context.action,
            original_strategy=context.original_strategy,
        )

        # ------------------------------------------------------------
        # 1. Saved locator
        # ------------------------------------------------------------

        if (
            allow_saved
            and self.config.prefer_saved_locator
        ):
            saved_result = self._try_saved_locator(
                context,
                probe,
            )

            if saved_result is not None:
                log_event(
                    "healing_completed",
                    identity=context.identity.element_key,
                    page_key=context.identity.page_key,
                    source=saved_result.source,
                )

                return saved_result

        # ------------------------------------------------------------
        # 2. Original locator
        # ------------------------------------------------------------

        original_result = self._try_original_locator(
            context,
            probe,
        )

        if original_result is not None:
            log_event(
                "healing_completed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                source=original_result.source,
            )

            return original_result

        # ------------------------------------------------------------
        # 3. Saved locator after original
        # ------------------------------------------------------------

        if (
            allow_saved
            and not self.config.prefer_saved_locator
        ):
            saved_result = self._try_saved_locator(
                context,
                probe,
            )

            if saved_result is not None:
                log_event(
                    "healing_completed",
                    identity=context.identity.element_key,
                    page_key=context.identity.page_key,
                    source=saved_result.source,
                )

                return saved_result

        # ------------------------------------------------------------
        # 4. AI disabled
        # ------------------------------------------------------------

        if (
            not allow_ai
            or not self.config.allow_ai
        ):
            message = (
                "Healing failed and AI is disabled."
            )

            log_event(
                "healing_failed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                error=message,
            )

            raise SelfHealingFailed(message)

        # ------------------------------------------------------------
        # 5. AI unavailable
        # ------------------------------------------------------------

        if self.locator_generator is None:
            message = (
                "Healing failed and no AI provider "
                "is configured."
            )

            log_event(
                "healing_failed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                error=message,
            )

            if self.config.fail_if_ai_unavailable:
                raise LLMProviderError(message)

            raise SelfHealingFailed(message)

        # ------------------------------------------------------------
        # 6. Generate candidates
        # ------------------------------------------------------------

        candidates = self._generate_ai_candidates(
            context
        )

        if not candidates:
            message = (
                "AI returned no valid locator candidates."
            )

            log_event(
                "healing_failed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                error=message,
            )

            raise SelfHealingFailed(message)

        # ------------------------------------------------------------
        # 7. Probe candidates against live DOM
        # ------------------------------------------------------------

        last_error = ""

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):
            success, error = self._probe_candidate(
                probe,
                candidate,
            )

            if success:
                self._save_success(
                    context,
                    candidate,
                )

                log_event(
                    "ai_candidate_success",
                    identity=context.identity.element_key,
                    page_key=context.identity.page_key,
                    candidate=candidate.value,
                    strategy=candidate.strategy,
                    candidate_index=index,
                )

                result = HealingResult(
                    success=True,
                    candidate=candidate,
                    source="ai_candidate",
                )

                log_event(
                    "healing_completed",
                    identity=context.identity.element_key,
                    page_key=context.identity.page_key,
                    source=result.source,
                )

                return result

            last_error = (
                error
                or "candidate did not resolve"
            )

            self._save_failure(
                context,
                candidate,
                last_error,
            )

            log_event(
                "ai_candidate_failed",
                identity=context.identity.element_key,
                page_key=context.identity.page_key,
                candidate=candidate.value,
                strategy=candidate.strategy,
                candidate_index=index,
                error=last_error,
            )

        # ------------------------------------------------------------
        # 8. No candidate succeeded
        # ------------------------------------------------------------

        message = (
            last_error
            or "No locator candidate could resolve "
            "the element."
        )

        log_event(
            "healing_failed",
            identity=context.identity.element_key,
            page_key=context.identity.page_key,
            error=message,
        )

        raise SelfHealingFailed(message)
