"""Shared adapter interface.

Adapters must never raise just because credentials are missing. They
return a skip reason and an empty list so the orchestrator can continue.
"""
from __future__ import annotations

import os
from typing import Any, Iterable

from ..schema import NormalizedProduct


def skip_result(reason: str) -> dict[str, Any]:
    return {"skipped": True, "reason": reason, "items": []}


class SourceAdapter:
    """One catalog source (Shopify store, affiliate network, or file feed)."""

    name = "base"
    env_vars: tuple[str, ...] = ()

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled"))

    def missing_env(self) -> list[str]:
        needed = tuple(self.config.get("env") or self.env_vars)
        return [k for k in needed if not os.environ.get(k)]

    def credentials_ok(self) -> bool:
        return not self.missing_env()

    def skip_reason(self) -> str | None:
        if not self.is_enabled():
            return f"{self.name}: disabled (default). Enable in brands.yml when you are ready."
        missing = self.missing_env()
        if missing:
            return f"{self.name}: skipped, missing credentials ({', '.join(missing)}). No accounts are created."
        return None

    def fetch(self) -> list[dict[str, Any]]:
        """Fetch raw records. Must be a no-op (return []) when skipped."""
        reason = self.skip_reason()
        if reason:
            return []
        return self._fetch()

    def _fetch(self) -> list[dict[str, Any]]:
        return []

    def normalize(self, records: Iterable[dict[str, Any]]) -> list[NormalizedProduct]:
        out: list[NormalizedProduct] = []
        for rec in records:
            item = self.normalize_one(rec)
            if item is not None:
                out.append(item)
        return out

    def normalize_one(self, rec: dict[str, Any]) -> NormalizedProduct | None:
        raise NotImplementedError

    def run(self) -> dict[str, Any]:
        reason = self.skip_reason()
        if reason:
            return skip_result(reason)
        raw = self._fetch()
        items = self.normalize(raw)
        return {"skipped": False, "reason": None, "raw": len(raw), "items": items}
