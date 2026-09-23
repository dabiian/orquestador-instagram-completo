"""Deterministic fake locator generator for tests."""

from __future__ import annotations

from ..core.models import HealingContext, LocatorCandidate
from .base import LocatorGenerator


class FakeLocatorGenerator(LocatorGenerator):
    def __init__(self, candidates: list[LocatorCandidate] | None = None) -> None:
        self._candidates = candidates or [
            LocatorCandidate(strategy="css", value='[data-testid="fallback"]', name="fallback-testid", confidence=0.9, reason="default test candidate"),
            LocatorCandidate(strategy="xpath", value='//input[@name="username"]', name="username-name", confidence=0.8, reason="default test candidate"),
        ]

    def generate(self, context: HealingContext) -> list[LocatorCandidate]:
        return list(self._candidates)