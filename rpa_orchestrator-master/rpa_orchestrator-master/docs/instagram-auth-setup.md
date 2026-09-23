# Instagram ↔ RPA Orchestrator authentication

There are **two different trust relationships**. Do not use the dashboard password as a token.

## A. Django adapter → Orchestrator WebSocket

The Django Instagram adapter is registered as the bot key:

```text
instagram-backend-01
```

The Orchestrator accepts worker tokens through `BOT_TOKENS`.

In the Orchestrator `.env`:

```env
BOT_TOKENS={"GENERATED_BOT_TOKEN":"instagram-backend-01"}
```

The same generated token goes in the Django backend as:

```env
ORCHESTRATOR_BOT_TOKEN=GENERATED_BOT_TOKEN
ORCHESTRATOR_BOT_KEY=instagram-backend-01
```

Generate a token locally with:

```powershell
python scripts/generate_instagram_integration_tokens.py
```

## B. Orchestrator → Django catalog/API

The Orchestrator has a separate setting:

```env
INSTAGRAM_BACKEND_URL=http://10.0.0.90:8004
INSTAGRAM_BACKEND_TOKEN=GENERATED_CATALOG_TOKEN
```

`INSTAGRAM_BACKEND_TOKEN` is **not** the worker token. It authenticates calls made by the Orchestrator to the Django Instagram backend catalog/API.

The Django backend must be configured to accept this catalog token using the authentication setting implemented by its integration adapter. Keep the value identical on both sides.

## Important

- `SeoAgent2026!$` is the dashboard password, not either integration token.
- Never commit populated `.env` files or generated secrets.
- Do not copy the example placeholders literally.
- Use different random values for the worker token and catalog token.
- `ORCHESTRATOR_API_TOKEN` is **not an Orchestrator setting** in this repository's `.env.example`; do not invent it on the Orchestrator side.

## Quick verification

After configuring both applications:

1. Start the Orchestrator.
2. Start Django with the Instagram adapter enabled.
3. Confirm the adapter registers as `instagram-backend-01`.
4. Confirm the Orchestrator can call the Django Instagram catalog.
5. Only then run a real Instagram execution.
