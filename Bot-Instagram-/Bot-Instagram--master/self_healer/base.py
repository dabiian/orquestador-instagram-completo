"""Legacy compatibility shim for the original self_healer module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SelfHealer:
    """Small compatibility wrapper kept for older imports.

    The real implementation now lives in the package modules under
    ``self_healer.core`` and ``self_healer.selenium_adapter``.
    """

    config: dict[str, Any] = field(default_factory=dict)

    def check(self) -> dict[str, Any]:
        return {"status": "ok", "issues": []}

    def heal(self) -> dict[str, Any]:
        return {"healed": False, "details": "no_action"}

    def run(self) -> dict[str, Any]:
        result = {"check": self.check(), "heal": None}
        if result["check"].get("status") != "ok":
            result["heal"] = self.heal()
        return result
