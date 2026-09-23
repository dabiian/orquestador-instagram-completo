"""Minimal REST API for the self_healer package.

This service keeps locator generation isolated from the main bot process.
The bot can send a browser snapshot and receive locator candidates over HTTP,
then validate them locally against the live Selenium session.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

from ..core.config import SelfHealerConfig
from ..core.exceptions import LLMProviderError
from ..core.models import HealingContext, LocatorCandidate, LocatorIdentity
from ..core.sqlite_store import SelfHealerStore
from ..providers.base import LocatorGenerator
from ..providers.fake_provider import FakeLocatorGenerator
from ..providers.openai_provider import OpenAILocatorGenerator

logger = logging.getLogger("self_healer.api")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _candidate_to_payload(candidate: LocatorCandidate) -> dict[str, Any]:
    return asdict(candidate)


def _identity_from_payload(payload: dict[str, Any]) -> LocatorIdentity:
    identity_payload = payload.get("identity")
    if not isinstance(identity_payload, dict):
        identity_payload = payload
    project_name = str(identity_payload.get("project_name", "")).strip()
    if not project_name:
        raise ValueError("identity.project_name is required")
    return LocatorIdentity(
        project_name=project_name,
        framework=str(identity_payload.get("framework", "selenium")),
        page_key=str(identity_payload.get("page_key", "default")),
        element_key=str(identity_payload.get("element_key", "")),
    )


def _context_from_payload(payload: dict[str, Any]) -> HealingContext:
    identity = _identity_from_payload(payload)
    url = str(payload.get("url", "")).strip()
    if not url:
        raise ValueError("url is required")
    original_strategy = str(payload.get("original_strategy", "")).strip()
    original_value = str(payload.get("original_value", "")).strip()
    html = str(payload.get("html", ""))
    if not original_strategy or not original_value:
        raise ValueError("original_strategy and original_value are required")
    return HealingContext(
        identity=identity,
        url=url,
        original_strategy=original_strategy,
        original_value=original_value,
        html=html,
        action=str(payload.get("action", "find_element")),
        error=str(payload.get("error", "")),
        target_description=str(payload.get("target_description", "")),
    )


def _candidate_from_payload(payload: dict[str, Any]) -> LocatorCandidate:
    candidate_payload = payload.get("candidate")
    if isinstance(candidate_payload, dict):
        payload = candidate_payload
    strategy = str(payload.get("strategy", "")).strip()
    value = str(payload.get("value", "")).strip()
    if not strategy or not value:
        raise ValueError("candidate.strategy and candidate.value are required")
    return LocatorCandidate(
        strategy=strategy,
        value=value,
        name=str(payload.get("name", "")),
        confidence=float(payload.get("confidence", 0.0) or 0.0),
        reason=str(payload.get("reason", "")),
    )


class HealingAPIService:
    def __init__(
        self,
        *,
        config: SelfHealerConfig,
        store: SelfHealerStore,
        locator_generator: LocatorGenerator,
    ) -> None:
        self.config = config
        self.store = store
        self.locator_generator = locator_generator

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "self_healer",
            "project_name": self.config.project_name,
            "allow_ai": self.config.allow_ai,
            "db_path": self.config.db_path,
        }

    def suggest(self, payload: dict[str, Any]) -> dict[str, Any]:

        context = _context_from_payload(payload)

        print("\n========== HEAL REQUEST ==========")

        print(
            "ELEMENT:",
            context.identity.element_key
        )

        print(
            "ORIGINAL:",
            context.original_value
        )

        print(
            "URL:",
            context.url
        )

        print(
            "HTML SIZE:",
            len(context.html)
        )

        print("==================================")

        # First, check if we already have a healed locator in the store

        try:

            best = self.store.get_best_locator(
                context.identity
            )

        except Exception:

            best = None

        if best is not None:

            print(
                "📚 Locator encontrada en SQLite"
            )

            print(
                "STRATEGY:",
                best.strategy
            )

            print(
                "VALUE:",
                best.value
            )

            return {

                "ok": True,

                "count": 1,

                "candidates": [
                    _candidate_to_payload(best)
                ],

                "from_store": True,

            }

        print(
            "🧠 Consultando generador IA..."
        )

        candidates = self.locator_generator.generate(
            context
        )

        print(
            f"🤖 Candidates generados: {len(candidates)}"
        )

        for i, candidate in enumerate(
            candidates,
            start=1
        ):

            print(
                f"\nCandidate #{i}"
            )

            print(
                "Strategy:",
                candidate.strategy
            )

            print(
                "Value:",
                candidate.value
            )

            print(
                "Confidence:",
                candidate.confidence
            )

            print(
                "Reason:",
                candidate.reason
            )

            print("\nHTML PREVIEW:\n")
            print("\nHTML LENGTH:", len(context.html))
            print(context.html[:3000])

        return {

            "ok": True,

            "count": len(candidates),

            "candidates": [

                _candidate_to_payload(candidate)

                for candidate in candidates

            ],

        }

    def feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        context = _context_from_payload(payload)
        candidate = _candidate_from_payload(payload)
        status = str(payload.get("status", "")).strip().lower()
        error = str(payload.get("error", "")).strip()
        if status == "success":
            self.store.save_success(context, candidate)
        elif status == "failure":
            self.store.save_failure(context, candidate, error)
        else:
            raise ValueError("status must be 'success' or 'failure'")
        return {"ok": True, "status": status}


def _build_locator_generator(config: SelfHealerConfig, provider_name: str) -> LocatorGenerator:
    normalized = provider_name.strip().lower()
    if normalized == "fake":
        return FakeLocatorGenerator()
    if normalized in {"openai", "deepseek", "default"}:
        return OpenAILocatorGenerator(max_candidates=config.max_ai_candidates)
    raise ValueError("provider must be one of: default, openai, deepseek, fake")


def create_service(
    *,
    project_name: str,
    db_path: str,
    allow_ai: bool,
    provider_name: str = "default",
    max_ai_candidates: int = 8,
) -> HealingAPIService:
    config = SelfHealerConfig(
        project_name=project_name,
        db_path=db_path,
        allow_ai=allow_ai,
        max_ai_candidates=max_ai_candidates,
    )
    store = SelfHealerStore(db_path=config.db_path, disable_after_failures=config.disable_after_failures)
    locator_generator = _build_locator_generator(config, provider_name)
    return HealingAPIService(config=config, store=store, locator_generator=locator_generator)


class HealingAPIHandler(BaseHTTPRequestHandler):
    service: HealingAPIService | None = None

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _log_heal_response(self, request_payload: dict[str, Any], response_payload: dict[str, Any]) -> None:
        """Persist /v1/heal request+response as JSON lines for debugging."""
        try:
            log_dir = os.path.join(".self_healer", "logs")
            os.makedirs(log_dir, exist_ok=True)
            filename = os.path.join(log_dir, "heal_responses.log")
            entry = {
                "ts": datetime.utcnow().isoformat() + "Z",
                "request": request_payload,
                "response": response_payload,
            }
            with open(filename, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover - non-critical logging
            logger.debug("Failed to write heal response log: %s", exc)

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        if not raw_body:
            return {}
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON body: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _handle(self, method: str) -> None:
        service = self.service
        if service is None:
            self._send_json(500, {"ok": False, "error": "service not configured"})
            return
        path = urlparse(self.path).path
        try:
            if method == "GET" and path == "/health":
                self._send_json(200, service.health())
                return
            if method == "POST" and path in {"/v1/suggest", "/v1/heal"}:
                payload = self._read_json()
                result = service.suggest(payload)
                if path == "/v1/heal":
                    try:
                        self._log_heal_response(payload, result)
                    except Exception:
                        pass
                self._send_json(200, result)
                return
            if method == "POST" and path == "/v1/feedback":
                payload = self._read_json()
                self._send_json(200, service.feedback(payload))
                return
            self._send_json(404, {"ok": False, "error": "route not found"})
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
        except LLMProviderError as exc:
            self._send_json(502, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive boundary
            logger.exception("Unhandled API error")
            self._send_json(500, {"ok": False, "error": str(exc)})

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._handle("POST")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - BaseHTTPRequestHandler API
        logger.info("%s - - %s", self.address_string(), format % args)


def run_server(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    project_name: str = "self-healer-api",
    db_path: str = ".self_healer/self_healer.sqlite3",
    allow_ai: bool = True,
    provider_name: str = "default",
    max_ai_candidates: int = 8,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    service = create_service(
        project_name=project_name,
        db_path=db_path,
        allow_ai=allow_ai,
        provider_name=provider_name,
        max_ai_candidates=max_ai_candidates,
    )
    HealingAPIHandler.service = service
    server = HTTPServer((host, port), HealingAPIHandler)
    logger.info("self_healer API listening on http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("self_healer API stopped")
    finally:
        server.server_close()
        service.store.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the self_healer REST API")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--project-name", default="self-healer-api")
    parser.add_argument("--db-path", default=".self_healer/self_healer.sqlite3")
    parser.add_argument("--provider", default="default", choices=["default", "openai", "deepseek", "fake"])
    parser.add_argument("--max-ai-candidates", type=int, default=8)
    parser.add_argument("--allow-ai", dest="allow_ai", action="store_true")
    parser.add_argument("--disable-ai", dest="allow_ai", action="store_false")
    parser.set_defaults(allow_ai=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    run_server(
        host=args.host,
        port=args.port,
        project_name=args.project_name,
        db_path=args.db_path,
        allow_ai=args.allow_ai,
        provider_name=args.provider,
        max_ai_candidates=args.max_ai_candidates,
    )


if __name__ == "__main__":
    main()