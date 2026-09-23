"""Configuration for the self_healer package."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SelfHealerConfig:
    """Runtime configuration for the Web/Selenium self-healing engine."""

    project_name: str

    # Persistence
    db_path: str = ".self_healer/self_healer.sqlite3"

    # Core behavior
    enabled: bool = True
    heal_on_find: bool = True
    heal_on_action: bool = True

    # Selenium / DOM limits
    timeout_seconds: int = 8
    max_html_chars: int = 120000
    chunk_size_kb: int = 50
    max_chunks_to_try: int = 5

    # AI
    max_ai_candidates: int = 8
    allow_ai: bool = True
    fail_if_ai_unavailable: bool = False

    # Locator persistence
    prefer_saved_locator: bool = True
    save_only_validated_locators: bool = True

    # Diagnostics
    screenshot_on_failure: bool = False
    html_snapshot_on_failure: bool = False
    log_level: str = "INFO"

    # Self-protection
    disable_after_failures: int = 5

    # Advanced behavior
    learning_mode: bool = False
    strict_mode: bool = False

    def __post_init__(self) -> None:
        """Validate and normalize configuration values."""

        # --------------------------------------------------------------
        # Project
        # --------------------------------------------------------------

        if self.project_name is None:
            raise ValueError("project_name is required")

        self.project_name = self.project_name.strip()

        if not self.project_name:
            raise ValueError("project_name is required")

        # --------------------------------------------------------------
        # Persistence
        # --------------------------------------------------------------

        if self.db_path is None:
            raise ValueError("db_path is required")

        self.db_path = str(self.db_path).strip()

        if not self.db_path:
            raise ValueError("db_path is required")

        # --------------------------------------------------------------
        # Numeric limits
        # --------------------------------------------------------------

        self.timeout_seconds = self._positive_int(
            self.timeout_seconds,
            "timeout_seconds",
        )

        self.max_ai_candidates = self._positive_int(
            self.max_ai_candidates,
            "max_ai_candidates",
        )

        self.max_html_chars = self._positive_int(
            self.max_html_chars,
            "max_html_chars",
        )

        self.chunk_size_kb = self._positive_int(
            self.chunk_size_kb,
            "chunk_size_kb",
        )

        self.max_chunks_to_try = self._positive_int(
            self.max_chunks_to_try,
            "max_chunks_to_try",
        )

        self.disable_after_failures = self._non_negative_int(
            self.disable_after_failures,
            "disable_after_failures",
        )

        # --------------------------------------------------------------
        # Log level
        # --------------------------------------------------------------

        if self.log_level is None:
            self.log_level = "INFO"

        self.log_level = str(
            self.log_level
        ).strip().upper()

        allowed_log_levels = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

        if self.log_level not in allowed_log_levels:
            raise ValueError(
                "log_level must be one of: "
                + ", ".join(sorted(allowed_log_levels))
            )

        # --------------------------------------------------------------
        # Boolean configuration
        # --------------------------------------------------------------

        boolean_fields = (
            "enabled",
            "heal_on_find",
            "heal_on_action",
            "prefer_saved_locator",
            "save_only_validated_locators",
            "allow_ai",
            "fail_if_ai_unavailable",
            "screenshot_on_failure",
            "html_snapshot_on_failure",
            "learning_mode",
            "strict_mode",
        )

        for field_name in boolean_fields:
            value = getattr(self, field_name)

            if not isinstance(value, bool):
                raise TypeError(
                    f"{field_name} must be a boolean"
                )

        # --------------------------------------------------------------
        # Configuration consistency
        # --------------------------------------------------------------

        if not self.allow_ai and self.fail_if_ai_unavailable:
            # There is no provider to fail against when AI is explicitly
            # disabled. Keep the configuration deterministic instead of
            # allowing a contradictory combination.
            self.fail_if_ai_unavailable = False

    @staticmethod
    def _positive_int(
        value: int,
        field_name: str,
    ) -> int:
        """Validate a strictly positive integer."""
        if isinstance(value, bool):
            raise TypeError(
                f"{field_name} must be an integer"
            )

        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"{field_name} must be an integer"
            ) from exc

        if value <= 0:
            raise ValueError(
                f"{field_name} must be positive"
            )

        return value

    @staticmethod
    def _non_negative_int(
        value: int,
        field_name: str,
    ) -> int:
        """Validate an integer that may be zero."""
        if isinstance(value, bool):
            raise TypeError(
                f"{field_name} must be an integer"
            )

        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"{field_name} must be an integer"
            ) from exc

        if value < 0:
            raise ValueError(
                f"{field_name} cannot be negative"
            )

        return value
