"""SQLite persistence for healed locators and healing events."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .candidate_validator import validate_candidate
from .models import HealingContext, LocatorCandidate, LocatorIdentity


logger = logging.getLogger("self_healer.sqlite_store")


def _utc_now() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _hash_text(value: str) -> str:
    """Return a stable SHA-256 hash for text."""
    return hashlib.sha256(
        (value or "").encode("utf-8", errors="ignore")
    ).hexdigest()


def _safe_error(error: object) -> str:
    """Convert an exception/error value into a bounded log/database string."""
    text = str(error or "").strip()

    # Prevent accidentally storing huge Selenium/LLM exception payloads.
    return text[:4000]


class SelfHealerStore:
    """Persistent SQLite store for healed locators and healing events."""

    def __init__(
        self,
        db_path: str = ".self_healer/self_healer.sqlite3",
        disable_after_failures: int = 5,
    ) -> None:
        if not isinstance(db_path, str) or not db_path.strip():
            raise ValueError("db_path must be a non-empty string")

        if not isinstance(disable_after_failures, int):
            raise TypeError("disable_after_failures must be an integer")

        if disable_after_failures < 0:
            raise ValueError("disable_after_failures cannot be negative")

        self.db_path = db_path
        self.disable_after_failures = disable_after_failures

        self._conn = self._connect(db_path)
        self._conn.row_factory = sqlite3.Row

        self._configure_connection()
        self._create_tables()

    # ------------------------------------------------------------------
    # Connection / schema
    # ------------------------------------------------------------------

    def _connect(self, db_path: str) -> sqlite3.Connection:
        """Open the SQLite database and create its parent directory."""
        if db_path == ":memory:":
            return sqlite3.connect(":memory:")

        path = Path(db_path).expanduser()

        if path.parent:
            path.parent.mkdir(parents=True, exist_ok=True)

        return sqlite3.connect(str(path))

    def _configure_connection(self) -> None:
        """Configure SQLite for reliable local persistence."""
        try:
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._conn.execute("PRAGMA busy_timeout=5000;")

            # WAL is useful for the normal file-backed database.
            # SQLite does not need it for :memory: databases.
            if self.db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL;")

        except sqlite3.Error:
            logger.exception("Failed to configure SQLite connection")
            raise

    def _create_tables(self) -> None:
        """Create the persistence schema if it does not already exist."""
        try:
            with self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS healed_locators (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,

                        project_name TEXT NOT NULL,
                        framework TEXT NOT NULL,
                        page_key TEXT NOT NULL,
                        element_key TEXT NOT NULL,

                        strategy TEXT NOT NULL,
                        value TEXT NOT NULL,
                        name TEXT NOT NULL DEFAULT '',

                        confidence REAL NOT NULL DEFAULT 0,
                        reason TEXT NOT NULL DEFAULT '',

                        source_html_hash TEXT NOT NULL DEFAULT '',
                        url_hash TEXT NOT NULL DEFAULT '',

                        successes INTEGER NOT NULL DEFAULT 0,
                        failures INTEGER NOT NULL DEFAULT 0,

                        enabled INTEGER NOT NULL DEFAULT 1,

                        last_error TEXT NOT NULL DEFAULT '',

                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,

                        UNIQUE(
                            project_name,
                            framework,
                            page_key,
                            element_key,
                            strategy,
                            value,
                            name
                        )
                    )
                    """
                )

                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS healing_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,

                        project_name TEXT NOT NULL,
                        framework TEXT NOT NULL,
                        page_key TEXT NOT NULL,
                        element_key TEXT NOT NULL,

                        url TEXT NOT NULL,

                        original_strategy TEXT NOT NULL,
                        original_value TEXT NOT NULL,

                        candidate_strategy TEXT NOT NULL,
                        candidate_value TEXT NOT NULL,
                        candidate_name TEXT NOT NULL,

                        action TEXT NOT NULL,
                        status TEXT NOT NULL,
                        error TEXT NOT NULL,

                        html_hash TEXT NOT NULL,

                        created_at TEXT NOT NULL
                    )
                    """
                )

                self._create_indexes()

        except sqlite3.Error:
            logger.exception("Failed to create Self-Healer database schema")
            raise

    def _create_indexes(self) -> None:
        """Create indexes used by locator lookup and event inspection."""
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_healed_locators_identity
            ON healed_locators (
                project_name,
                framework,
                page_key,
                element_key
            )
            """
        )

        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_healing_events_identity
            ON healing_events (
                project_name,
                framework,
                page_key,
                element_key,
                created_at
            )
            """
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _identity_params(
        self,
        identity: LocatorIdentity,
    ) -> tuple[str, str, str, str]:
        """Convert a locator identity into SQL parameters."""
        return (
            identity.project_name,
            identity.framework,
            identity.page_key,
            identity.element_key,
        )

    def _candidate_params(
        self,
        candidate: LocatorCandidate,
    ) -> tuple[str, str, str]:
        """Convert a locator candidate into SQL parameters."""
        return (
            candidate.strategy,
            candidate.value,
            candidate.name,
        )

    def _validate_candidate(
        self,
        candidate: LocatorCandidate,
    ) -> LocatorCandidate:
        """Validate and normalize a candidate before persistence."""
        return validate_candidate(candidate)

    # ------------------------------------------------------------------
    # Locator persistence
    # ------------------------------------------------------------------

    def _upsert_locator(
        self,
        identity: LocatorIdentity,
        candidate: LocatorCandidate,
        *,
        success_delta: int = 0,
        failure_delta: int = 0,
        error: str = "",
        enabled: int | None = None,
        context: HealingContext | None = None,
    ) -> None:
        """Insert or update a locator record."""
        candidate = self._validate_candidate(candidate)

        if not isinstance(success_delta, int):
            raise TypeError("success_delta must be an integer")

        if not isinstance(failure_delta, int):
            raise TypeError("failure_delta must be an integer")

        if success_delta < 0:
            raise ValueError("success_delta cannot be negative")

        if failure_delta < 0:
            raise ValueError("failure_delta cannot be negative")

        if enabled is not None:
            enabled = 1 if bool(enabled) else 0

        error_text = _safe_error(error)

        html_hash = _hash_text(context.html if context else "")
        url_hash = _hash_text(context.url if context else "")

        now = _utc_now()

        (
            project_name,
            framework,
            page_key,
            element_key,
        ) = self._identity_params(identity)

        strategy, value, name = self._candidate_params(candidate)

        try:
            with self._conn:
                existing = self._conn.execute(
                    """
                    SELECT
                        id,
                        successes,
                        failures,
                        enabled
                    FROM healed_locators
                    WHERE
                        project_name=?
                        AND framework=?
                        AND page_key=?
                        AND element_key=?
                        AND strategy=?
                        AND value=?
                        AND name=?
                    """,
                    (
                        project_name,
                        framework,
                        page_key,
                        element_key,
                        strategy,
                        value,
                        name,
                    ),
                ).fetchone()

                if existing is None:
                    successes = success_delta
                    failures = failure_delta

                    enabled_value = (
                        1
                        if enabled is None
                        else enabled
                    )

                    if (
                        self.disable_after_failures
                        and failures >= self.disable_after_failures
                    ):
                        enabled_value = 0

                    self._conn.execute(
                        """
                        INSERT INTO healed_locators (
                            project_name,
                            framework,
                            page_key,
                            element_key,
                            strategy,
                            value,
                            name,
                            confidence,
                            reason,
                            source_html_hash,
                            url_hash,
                            successes,
                            failures,
                            enabled,
                            last_error,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            project_name,
                            framework,
                            page_key,
                            element_key,
                            strategy,
                            value,
                            name,
                            candidate.confidence,
                            candidate.reason,
                            html_hash,
                            url_hash,
                            successes,
                            failures,
                            enabled_value,
                            error_text,
                            now,
                            now,
                        ),
                    )

                    return

                locator_id = int(existing["id"])

                successes = (
                    int(existing["successes"])
                    + success_delta
                )

                failures = (
                    int(existing["failures"])
                    + failure_delta
                )

                enabled_value = int(existing["enabled"])

                if enabled is not None:
                    enabled_value = enabled

                if (
                    self.disable_after_failures
                    and failures >= self.disable_after_failures
                ):
                    enabled_value = 0

                # A successful validation should always reactivate the
                # locator. This is important if a locator previously became
                # disabled and later proves valid again.
                if success_delta > 0:
                    enabled_value = 1

                self._conn.execute(
                    """
                    UPDATE healed_locators
                    SET
                        confidence=?,
                        reason=?,
                        source_html_hash=?,
                        url_hash=?,
                        successes=?,
                        failures=?,
                        enabled=?,
                        last_error=?,
                        updated_at=?
                    WHERE id=?
                    """,
                    (
                        candidate.confidence,
                        candidate.reason,
                        html_hash,
                        url_hash,
                        successes,
                        failures,
                        enabled_value,
                        error_text,
                        now,
                        locator_id,
                    ),
                )

        except sqlite3.Error:
            logger.exception(
                "Failed to upsert healed locator",
                extra={
                    "project_name": project_name,
                    "framework": framework,
                    "page_key": page_key,
                    "element_key": element_key,
                    "strategy": strategy,
                },
            )
            raise

    def _insert_event(
        self,
        context: HealingContext,
        candidate: LocatorCandidate,
        status: str,
        error: str = "",
    ) -> None:
        """Persist a healing event."""
        candidate = self._validate_candidate(candidate)

        status = str(status).strip() or "unknown"
        error_text = _safe_error(error)

        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO healing_events (
                        project_name,
                        framework,
                        page_key,
                        element_key,
                        url,
                        original_strategy,
                        original_value,
                        candidate_strategy,
                        candidate_value,
                        candidate_name,
                        action,
                        status,
                        error,
                        html_hash,
                        created_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        context.identity.project_name,
                        context.identity.framework,
                        context.identity.page_key,
                        context.identity.element_key,
                        context.url,
                        context.original_strategy,
                        context.original_value,
                        candidate.strategy,
                        candidate.value,
                        candidate.name,
                        context.action,
                        status,
                        error_text,
                        _hash_text(context.html),
                        _utc_now(),
                    ),
                )

        except sqlite3.Error:
            logger.exception(
                "Failed to insert healing event",
                extra={
                    "project_name": context.identity.project_name,
                    "framework": context.identity.framework,
                    "page_key": context.identity.page_key,
                    "element_key": context.identity.element_key,
                    "status": status,
                },
            )
            raise

    # ------------------------------------------------------------------
    # Locator lookup
    # ------------------------------------------------------------------

    def get_best_locator(
        self,
        identity: LocatorIdentity,
    ) -> LocatorCandidate | None:
        """Return the strongest currently enabled locator for an identity."""
        try:
            row = self._conn.execute(
                """
                SELECT
                    strategy,
                    value,
                    name,
                    confidence,
                    reason
                FROM healed_locators
                WHERE
                    project_name=?
                    AND framework=?
                    AND page_key=?
                    AND element_key=?
                    AND enabled=1
                ORDER BY
                    successes DESC,
                    confidence DESC,
                    failures ASC,
                    updated_at DESC,
                    id DESC
                LIMIT 1
                """,
                self._identity_params(identity),
            ).fetchone()

        except sqlite3.Error:
            logger.exception(
                "Failed to retrieve best locator",
                extra={
                    "project_name": identity.project_name,
                    "framework": identity.framework,
                    "page_key": identity.page_key,
                    "element_key": identity.element_key,
                },
            )
            return None

        if row is None:
            return None

        candidate = LocatorCandidate(
            strategy=row["strategy"],
            value=row["value"],
            name=row["name"],
            confidence=float(row["confidence"]),
            reason=row["reason"],
        )

        try:
            return self._validate_candidate(candidate)
        except Exception:
            logger.warning(
                "Ignoring invalid locator stored in database",
                extra={
                    "strategy": row["strategy"],
                    "element_key": identity.element_key,
                },
            )
            return None

    # ------------------------------------------------------------------
    # Public persistence API
    # ------------------------------------------------------------------

    def save_success(
        self,
        context: HealingContext,
        candidate: LocatorCandidate,
    ) -> None:
        """Record a successfully validated locator."""
        candidate = self._validate_candidate(candidate)

        self._upsert_locator(
            context.identity,
            candidate,
            success_delta=1,
            context=context,
        )

        try:
            self._insert_event(
                context,
                candidate,
                "success",
            )
        except sqlite3.Error:
            # Locator persistence already succeeded. Do not make the
            # successful healing operation fail solely because telemetry
            # persistence failed.
            logger.exception("Failed to persist success event")

    def save_failure(
        self,
        context: HealingContext,
        candidate: LocatorCandidate,
        error: str,
    ) -> None:
        """Record a failed locator validation/probe."""
        candidate = self._validate_candidate(candidate)

        error_text = _safe_error(error)

        self._upsert_locator(
            context.identity,
            candidate,
            failure_delta=1,
            error=error_text,
            context=context,
        )

        try:
            self._insert_event(
                context,
                candidate,
                "failure",
                error_text,
            )
        except sqlite3.Error:
            logger.exception("Failed to persist failure event")

    def disable_locator(
        self,
        identity: LocatorIdentity,
        candidate: LocatorCandidate,
    ) -> None:
        """Explicitly disable a locator."""
        candidate = self._validate_candidate(candidate)

        self._upsert_locator(
            identity,
            candidate,
            enabled=0,
        )

    def mark_locator_failure(
        self,
        identity: LocatorIdentity,
        candidate: LocatorCandidate,
        error: str,
    ) -> None:
        """Increment the failure count for a locator."""
        candidate = self._validate_candidate(candidate)

        self._upsert_locator(
            identity,
            candidate,
            failure_delta=1,
            error=_safe_error(error),
        )

    def list_locators(
        self,
        identity: LocatorIdentity,
    ) -> list[dict[str, Any]]:
        """Return all stored locators for an element identity."""
        try:
            rows = self._conn.execute(
                """
                SELECT *
                FROM healed_locators
                WHERE
                    project_name=?
                    AND framework=?
                    AND page_key=?
                    AND element_key=?
                ORDER BY
                    enabled DESC,
                    successes DESC,
                    confidence DESC,
                    failures ASC,
                    updated_at DESC,
                    id DESC
                """,
                self._identity_params(identity),
            ).fetchall()

        except sqlite3.Error:
            logger.exception(
                "Failed to list stored locators",
                extra={
                    "project_name": identity.project_name,
                    "framework": identity.framework,
                    "page_key": identity.page_key,
                    "element_key": identity.element_key,
                },
            )
            return []

        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the SQLite connection."""
        if getattr(self, "_conn", None) is None:
            return

        try:
            self._conn.close()
        finally:
            self._conn = None  # type: ignore[assignment]

    def __enter__(self) -> "SelfHealerStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        self.close()
