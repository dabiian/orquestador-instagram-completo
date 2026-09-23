"""Base interface for locator generators."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.models import HealingContext, LocatorCandidate


class LocatorGenerator(ABC):
    @abstractmethod
    def generate(self, context: HealingContext) -> list[LocatorCandidate]:
        raise NotImplementedError