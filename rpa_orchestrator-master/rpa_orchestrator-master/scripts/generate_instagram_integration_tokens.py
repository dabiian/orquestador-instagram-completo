#!/usr/bin/env python3
"""Generate local secrets for the Instagram ↔ RPA Orchestrator integration.

This script never commits or stores secrets in git. It only prints the exact
values/lines needed by the two applications.
"""

from __future__ import annotations

import json
import secrets


BOT_KEY = "instagram-backend-01"


def main() -> None:
    bot_token = secrets.token_urlsafe(48)
    catalog_token = secrets.token_urlsafe(48)

    bot_tokens = json.dumps({bot_token: BOT_KEY}, separators=(",", ":"))

    print("\n=== Instagram integration secrets ===\n")
    print("1) RPA Orchestrator .env")
    print(f"BOT_TOKENS={bot_tokens}")
    print(f"INSTAGRAM_BACKEND_TOKEN={catalog_token}")
    print("\n2) Django backend .env")
    print(f"ORCHESTRATOR_BOT_TOKEN={bot_token}")
    print(f"ORCHESTRATOR_BOT_KEY={BOT_KEY}")
    print(f"INSTAGRAM_ORCHESTRATOR_TOKEN={catalog_token}")
    print("\nContract:")
    print("  Django -> Orchestrator: ORCHESTRATOR_BOT_TOKEN == key in BOT_TOKENS")
    print("  Orchestrator -> Django: INSTAGRAM_BACKEND_TOKEN == INSTAGRAM_ORCHESTRATOR_TOKEN")
    print("\nKeep these values secret. Do NOT commit a populated .env file.\n")


if __name__ == "__main__":
    main()
