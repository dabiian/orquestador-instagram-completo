"""LLM provider for Web/HTML/Selenium locator self-healing.

This module generates alternative CSS/XPath locators from HTML DOM
provided by Selenium.

The LLM only proposes candidates.

Candidate validation must be performed locally by the self-healer
against the live Selenium DOM before a locator is accepted.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from ..core.exceptions import LLMProviderError
from ..core.hint_extractor import rank_chunks_by_locator_hints
from ..core.html_chunker import chunk_html
from ..core.models import HealingContext, LocatorCandidate
from .base import LocatorGenerator

logger = logging.getLogger(__name__)


# ================================================================
# ENVIRONMENT
# ================================================================


def _load_local_env() -> dict[str, str]:
    """Load values from self_healer/.env.

    Expected location:

        self_healer/.env

    System environment variables are handled by the OpenAI SDK.
    This function only loads the local project .env file.
    """

    env_path = (
        Path(__file__).resolve().parents[1] / ".env"
    )

    if not env_path.exists():
        return {}

    try:
        from dotenv import dotenv_values

    except Exception:
        logger.warning(
            "python-dotenv is not installed. "
            "Only system environment variables will be used."
        )
        return {}

    try:
        values = dotenv_values(env_path)

    except Exception as exc:
        logger.warning(
            "Failed to load local .env file: %s",
            exc,
        )
        return {}

    return {
        key: value
        for key, value in values.items()
        if value is not None
    }


def _normalize_env_value(
    value: str | None,
) -> str | None:
    """Normalize an environment/configuration value."""

    if value is None:
        return None

    value = str(value).strip()

    return value or None


# ================================================================
# PROVIDER
# ================================================================


class OpenAILocatorGenerator(LocatorGenerator):
    """LLM locator generator for Web/HTML/Selenium.

    Supported locator strategies:

        - css
        - xpath

    The LLM does not interact with Selenium directly.

    Flow:

        Selenium
            ↓
        HTML DOM
            ↓
        Self-Healer
            ↓
        LLM
            ↓
        CSS/XPath candidates
            ↓
        Local candidate validation
    """

    def __init__(
        self,
        model: str = "gpt-5",
        client: Any | None = None,
        max_candidates: int = 8,
        chunk_size_kb: int = 250,
        max_chunks_to_try: int = 25,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model
        self.client = client

        self.max_candidates = max(
            1,
            int(max_candidates),
        )

        self.chunk_size_kb = max(
            1,
            int(chunk_size_kb),
        )

        self.max_chunks_to_try = max(
            1,
            int(max_chunks_to_try),
        )

        # --------------------------------------------------------
        # Load local .env
        # --------------------------------------------------------

        local_env = _load_local_env()

        # --------------------------------------------------------
        # API key priority
        #
        # Explicit constructor argument
        #     ↓
        # DEEPSEEK_API_KEY
        #     ↓
        # OPENAI_API_KEY
        #
        # This preserves compatibility with the existing project.
        # --------------------------------------------------------

        self.api_key = (
            _normalize_env_value(api_key)
            or _normalize_env_value(os.getenv("DEEPSEEK_API_KEY"))
            or _normalize_env_value(os.getenv("OPENAI_API_KEY"))
            or _normalize_env_value(local_env.get("DEEPSEEK_API_KEY"))
            or _normalize_env_value(local_env.get("OPENAI_API_KEY"))
        )

        # --------------------------------------------------------
        # Base URL priority
        # --------------------------------------------------------

        self.base_url = (
            _normalize_env_value(base_url)
            or _normalize_env_value(os.getenv("DEEPSEEK_BASE_URL"))
            or _normalize_env_value(os.getenv("OPENAI_BASE_URL"))
            or _normalize_env_value(local_env.get("DEEPSEEK_BASE_URL"))
            or _normalize_env_value(local_env.get("OPENAI_BASE_URL"))
        )

    # ============================================================
    # SYSTEM PROMPT
    # ============================================================

    def _build_system_prompt(self) -> str:
        """Build the Web/Selenium system prompt."""

        return """
You are a Web Selenium self-healing locator engine.

You analyze HTML DOM captured from a real browser.

Your job is to find alternative Selenium locators when the
original locator is broken.

The target is a WEB APPLICATION.

The browser is controlled by Selenium.

The provided HTML is the source of truth.

You ONLY propose locators.

You do NOT execute Selenium.

You do NOT generate Python code.

You do NOT generate JavaScript.

You ONLY return valid JSON.

NEVER return markdown.

NEVER explain anything outside the JSON response.

============================================================
OUTPUT FORMAT
============================================================

Return exactly:

{
  "candidates": [
    {
      "strategy": "css",
      "value": "button[aria-label='Send']",
      "name": "Send button",
      "confidence": 0.97,
      "reason": "The button has a stable aria-label."
    }
  ]
}

============================================================
SUPPORTED STRATEGIES
============================================================

Only:

- css
- xpath

Never return:

- android
- appium
- uiautomator
- resource-id
- accessibility id
- javascript
- selenium
- Python
- JavaScript
- Playwright-specific locator syntax

============================================================
IMPORTANT SOURCE-OF-TRUTH RULE
============================================================

ONLY use elements and attributes that actually appear in the
provided HTML.

NEVER invent:

- tags
- attributes
- IDs
- classes
- ARIA labels
- data attributes
- text
- DOM relationships

If the provided HTML does not contain enough information to
identify the target reliably, return fewer candidates.

Do NOT hallucinate.

============================================================
LOCATOR PRIORITY
============================================================

Prefer stable semantic attributes.

Priority:

1. data-testid
2. data-test
3. data-qa
4. other stable data-* attributes
5. aria-label
6. aria-labelledby
7. name
8. stable id
9. placeholder
10. title
11. role
12. visible text
13. stable combinations
14. DOM relationships

Avoid generated framework classes.

Examples of unstable classes:

.css-1abc123

.sc-a1b2c3

._abc123

[class*="generated"]

============================================================
CSS PREFERENCE
============================================================

Prefer CSS when it is shorter and sufficiently reliable.

Good:

button[aria-label="Send"]

input[name="username"]

textarea[placeholder="Write a comment"]

button[data-testid="send"]

button[type="submit"]

Bad:

body > div:nth-child(4) > div:nth-child(2) > button

div:nth-child(7) > div:nth-child(2)

Selectors based entirely on generated classes.

============================================================
XPATH PREFERENCE
============================================================

Use XPath when it is more reliable than CSS.

Good:

//button[@aria-label='Send']

//input[@name='username']

//textarea[@placeholder='Write a comment']

//button[contains(normalize-space(.), 'Send')]

//div[@role='button' and @aria-label='Follow']

Avoid absolute XPath:

/html/body/div[1]/div[2]/div[3]

Avoid excessive indexes.

Avoid extremely long XPath.

============================================================
TEXT RULES
============================================================

Visible text can change because of:

- localization
- language
- capitalization
- A/B tests
- UI changes

Do not rely exclusively on visible text when stable attributes
are available.

If text is necessary, prefer robust XPath such as:

contains(normalize-space(.), 'Send')

instead of brittle exact text matching.

============================================================
DYNAMIC WEB APPLICATIONS
============================================================

The application may use:

- React
- Vue
- Angular
- dynamically generated classes
- dynamic IDs
- nested components
- duplicated elements
- ARIA roles
- hidden elements

Prefer semantic attributes.

If multiple elements match, combine stable attributes.

The target should ideally identify one interactable element.

============================================================
CHUNK CONTEXT
============================================================

The provided HTML may be only a FRAGMENT of the complete DOM.

Do not assume that the fragment starts at <html> or <body>.

Do not invent ancestors that are not visible.

Do not use relationships that cannot be verified from the
provided fragment.

============================================================
CONFIDENCE
============================================================

Confidence must be between:

0.0 and 1.0

Use high confidence only when the HTML strongly supports the
candidate.

Examples:

0.95 - very strong unique semantic selector

0.80 - strong selector with good attributes

0.60 - plausible but ambiguous

0.40 - weak fallback

Do not assign high confidence to speculative selectors.

============================================================
DUPLICATES
============================================================

Do not return duplicate candidates.

Order candidates from strongest to weakest.

============================================================
FINAL RULE
============================================================

Return ONLY JSON.

No markdown.

No explanation.

No comments.

No Python.

No JavaScript.

No Selenium code.

Only JSON.
"""

    # ============================================================
    # USER PROMPT
    # ============================================================

    def _build_user_prompt(
        self,
        context: HealingContext,
    ) -> str:
        """Build the Web/Selenium healing request."""

        identity = context.identity

        element_key = (
            identity.element_key
            if identity
            else ""
        )

        project_name = (
            identity.project_name
            if identity
            else ""
        )

        page_key = (
            identity.page_key
            if identity
            else ""
        )

        html = context.html or ""

        return f"""
Find the correct Web Selenium element in the HTML DOM provided
below.

============================================================
PROJECT
============================================================

{project_name}

============================================================
PAGE KEY
============================================================

{page_key}

============================================================
ELEMENT KEY
============================================================

{element_key}

============================================================
TARGET DESCRIPTION
============================================================

{context.target_description}

Locator hint: {context.target_description or element_key}

============================================================
ORIGINAL LOCATOR STRATEGY
============================================================

{context.original_strategy}

============================================================
BROKEN LOCATOR
============================================================

{context.original_value}

============================================================
ACTION
============================================================

{context.action}

============================================================
PAGE URL
============================================================

{context.url}

============================================================
ERROR
============================================================

{context.error}

============================================================
HTML DOM / DOM FRAGMENT
============================================================

{html}

============================================================
INSTRUCTIONS
============================================================

The HTML above is the source of truth.

Generate Selenium-compatible CSS or XPath locators.

Only use elements and attributes that actually appear in the
provided HTML.

Do not invent selectors.

Do not invent attributes.

Do not invent text.

Do not assume missing ancestors.

If the HTML fragment is insufficient, return fewer candidates.

Return only JSON.
"""

    # ============================================================
    # RESPONSE TEXT EXTRACTION
    # ============================================================

    def _extract_text(
        self,
        response: Any,
    ) -> str:
        """Extract textual content from an LLM response."""

        try:

            if response is None:
                return ""

            if isinstance(response, str):
                return response

            # Newer response APIs.
            if hasattr(response, "output_text"):

                output_text = response.output_text

                if output_text:
                    return str(output_text)

            # Chat completion API.
            if hasattr(response, "choices"):

                choices = response.choices

                if not choices:
                    return ""

                choice = choices[0]

                # Standard chat completion.
                if hasattr(choice, "message"):

                    message = choice.message

                    if hasattr(
                        message,
                        "content",
                    ):

                        content = message.content

                        if content is not None:
                            return str(content)

                # Legacy completion.
                if hasattr(
                    choice,
                    "text",
                ):

                    text = choice.text

                    if text is not None:
                        return str(text)

            return str(response)

        except Exception as exc:

            logger.warning(
                "Failed to extract LLM response text: %s",
                exc,
            )

            return str(response)

    # ============================================================
    # JSON CLEANING
    # ============================================================

    def _clean_json(
        self,
        text: str,
    ) -> str:
        """Clean accidental markdown/code fences."""

        if not text:
            return ""

        text = text.strip()

        # Remove ```json ... ```
        if text.startswith("```json"):

            text = text[
                len("```json"):
            ].strip()

        # Remove ``` ... ```
        elif text.startswith("```"):

            text = text[
                len("```"):
            ].strip()

        if text.endswith("```"):

            text = text[
                :-len("```")
            ].strip()

        return text

    # ============================================================
    # CONFIDENCE
    # ============================================================

    def _normalize_confidence(
        self,
        value: Any,
    ) -> float:
        """Normalize LLM confidence to a float between 0 and 1."""

        try:

            if isinstance(value, str):

                lower = (
                    value
                    .lower()
                    .strip()
                )

                mapping = {
                    "very high": 0.95,
                    "high": 0.85,
                    "medium": 0.60,
                    "low": 0.30,
                    "very low": 0.10,
                }

                if lower in mapping:
                    return mapping[lower]

            value = float(value)

            # Support percentages:
            #
            # 97 -> 0.97
            #
            if value > 1:
                value /= 100.0

            return max(
                0.0,
                min(
                    value,
                    1.0,
                ),
            )

        except Exception:

            return 0.5

    # ============================================================
    # STRATEGY
    # ============================================================

    def _normalize_strategy(
        self,
        strategy: Any,
    ) -> str | None:
        """Normalize a strategy returned by the LLM."""

        if strategy is None:
            return None

        strategy = (
            str(strategy)
            .strip()
            .lower()
        )

        aliases = {
            "xpath": "xpath",
            "x-path": "xpath",
            "x_path": "xpath",

            "css": "css",
            "css selector": "css",
            "css_selector": "css",
            "css-selector": "css",
        }

        return aliases.get(
            strategy
        )

    # ============================================================
    # PARSER
    # ============================================================

    def _parse_candidates(
        self,
        payload: str,
    ) -> list[LocatorCandidate]:
        """Parse LLM JSON into LocatorCandidate objects."""

        payload = self._clean_json(
            payload
        )

        if not payload:
            return []

        # --------------------------------------------------------
        # Parse JSON
        # --------------------------------------------------------

        try:

            data = json.loads(
                payload
            )

        except Exception as exc:

            logger.warning(
                "Invalid JSON returned by LLM: %s",
                exc,
            )

            logger.debug(
                "LLM payload: %s",
                payload,
            )

            return []

        # --------------------------------------------------------
        # Extract candidate list
        # --------------------------------------------------------

        raw_candidates: list[Any] = []

        if isinstance(
            data,
            dict,
        ):

            candidates_value = data.get(
                "candidates"
            )

            if isinstance(
                candidates_value,
                list,
            ):

                raw_candidates = (
                    candidates_value
                )

            # Compatibility with alternative response structures.
            if not raw_candidates:

                for key in (
                    "result",
                    "items",
                    "locators",
                    "choices",
                ):

                    alternative = data.get(
                        key
                    )

                    if isinstance(
                        alternative,
                        list,
                    ):

                        raw_candidates = (
                            alternative
                        )

                        break

        elif isinstance(
            data,
            list,
        ):

            raw_candidates = data

        # --------------------------------------------------------
        # Parse individual candidates
        # --------------------------------------------------------

        candidates: list[
            LocatorCandidate
        ] = []

        for item in raw_candidates:

            try:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                value = str(
                    item.get(
                        "value",
                        "",
                    )
                ).strip()

                if not value:
                    continue

                strategy = (
                    self._normalize_strategy(
                        item.get(
                            "strategy"
                        )
                    )
                )

                if strategy not in {
                    "css",
                    "xpath",
                }:

                    logger.debug(
                        "Ignoring unsupported locator strategy: %r",
                        item.get(
                            "strategy"
                        ),
                    )

                    continue

                confidence = (
                    self._normalize_confidence(
                        item.get(
                            "confidence",
                            0.5,
                        )
                    )
                )

                name = str(
                    item.get(
                        "name",
                        "",
                    )
                ).strip()

                reason = str(
                    item.get(
                        "reason",
                        "",
                    )
                ).strip()

                candidate = LocatorCandidate(
                    strategy=strategy,
                    value=value,
                    name=name,
                    confidence=confidence,
                    reason=reason,
                )

                candidates.append(
                    candidate
                )

            except Exception as exc:

                logger.warning(
                    "Invalid locator candidate: %s",
                    exc,
                )

        # --------------------------------------------------------
        # Deduplicate
        #
        # Same strategy + same value = same locator.
        # --------------------------------------------------------

        unique: dict[
            tuple[str, str],
            LocatorCandidate,
        ] = {}

        for candidate in candidates:

            key = (
                candidate.strategy,
                candidate.value,
            )

            existing = unique.get(
                key
            )

            if existing is None:

                unique[key] = candidate

            elif (
                candidate.confidence
                > existing.confidence
            ):

                unique[key] = candidate

        candidates = list(
            unique.values()
        )

        # --------------------------------------------------------
        # Strongest first
        # --------------------------------------------------------

        candidates.sort(
            key=lambda candidate:
                candidate.confidence,
            reverse=True,
        )

        return candidates[
            : self.max_candidates
        ]

    # ============================================================
    # CHAT COMPLETION
    # ============================================================

    def _chat_completion(
        self,
        client: Any,
        messages: list[
            dict[str, str]
        ],
    ) -> Any:
        """Call the chat completion API.

        First tries structured JSON output.

        If the provider does not support response_format,
        retries without it.
        """

        try:

            return client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={
                    "type": "json_object",
                },
                messages=messages,
            )

        except Exception as exc:

            message = str(
                exc
            ).lower()

            # Some OpenAI-compatible providers do not support
            # response_format=json_object.
            if (
                "response_format"
                in message
                or "json_object"
                in message
                or "structured output"
                in message
            ):

                logger.warning(
                    "Provider does not support structured JSON "
                    "responses. Retrying without response_format."
                )

                return client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    messages=messages,
                )

            raise

    # ============================================================
    # SINGLE DOM CHUNK
    # ============================================================

    def _generate_single_chunk(
        self,
        context: HealingContext,
        client: Any,
    ) -> list[LocatorCandidate]:
        """Generate locator candidates from one DOM chunk."""

        html_length = len(
            context.html or ""
        )

        logger.debug(
            "Generating Web locator candidates. "
            "HTML fragment length=%s",
            html_length,
        )

        messages = [
            {
                "role": "system",
                "content": (
                    self._build_system_prompt()
                ),
            },
            {
                "role": "user",
                "content": (
                    self._build_user_prompt(
                        context
                    )
                ),
            },
        ]

        response = self._chat_completion(
            client,
            messages,
        )

        text = self._extract_text(
            response
        )

        # Do NOT log the full LLM response at INFO level.
        # It can contain large DOM-related content.
        logger.debug(
            "Web self-healer LLM response length=%s",
            len(text),
        )

        candidates = (
            self._parse_candidates(
                text
            )
        )

        logger.info(
            "LLM generated %s Web locator candidates.",
            len(candidates),
        )

        return candidates

    # ============================================================
    # CHUNKING
    # ============================================================

    def generate_with_chunking(
        self,
        context: HealingContext,
        client: Any,
    ) -> list[LocatorCandidate]:
        """Generate locator candidates using relevant DOM chunks."""

        if not context.html:

            logger.warning(
                "Empty HTML received by Web self-healer."
            )

            return []

        logger.info(
            "Web self-healer received HTML. "
            "length=%s target=%s locator=%s",
            len(context.html),
            context.target_description,
            context.original_value,
        )

        # --------------------------------------------------------
        # Split DOM into chunks
        # --------------------------------------------------------

        chunks = chunk_html(
            context.html,
            self.chunk_size_kb,
        )

        if not chunks:

            logger.warning(
                "No HTML chunks generated."
            )

            return []

        logger.info(
            "Generated %s HTML chunks.",
            len(chunks),
        )

        # --------------------------------------------------------
        # Rank chunks according to the original locator.
        #
        # IMPORTANT:
        # This now supports BOTH:
        #
        #   XPath
        #   CSS
        #
        # --------------------------------------------------------

        ranked_chunks = (
            rank_chunks_by_locator_hints(
                chunks=chunks,
                broken_locator=(
                    context.original_value
                ),
                top_k=(
                    self.max_chunks_to_try
                ),
                include_neighbors=True,
            )
        )

        # --------------------------------------------------------
        # Fallback if no hints matched.
        # --------------------------------------------------------

        if not ranked_chunks:

            logger.warning(
                "No relevant HTML chunks found from locator hints. "
                "Using first chunks as fallback."
            )

            ranked_chunks = [
                {
                    "chunk": chunk,
                    "score": 0.0,
                    "index": index,
                }
                for index, chunk in enumerate(
                    chunks[
                        : self.max_chunks_to_try
                    ]
                )
            ]

        logger.info(
            "Trying %s relevant HTML chunks.",
            len(ranked_chunks),
        )

        # --------------------------------------------------------
        # Generate candidates
        # --------------------------------------------------------

        all_candidates: list[
            LocatorCandidate
        ] = []

        for position, chunk_info in enumerate(
            ranked_chunks
        ):

            logger.debug(
                "Processing HTML chunk %s/%s "
                "(source index=%s score=%.2f)",
                position + 1,
                len(ranked_chunks),
                chunk_info.get(
                    "index",
                    -1,
                ),
                float(
                    chunk_info.get(
                        "score",
                        0.0,
                    )
                ),
            )

            chunk = chunk_info.get(
                "chunk",
                "",
            )

            if not chunk:
                continue

            # ----------------------------------------------------
            # Create context for this fragment.
            # ----------------------------------------------------

            chunked_context = HealingContext(
                identity=context.identity,
                url=context.url,
                original_strategy=(
                    context.original_strategy
                ),
                original_value=(
                    context.original_value
                ),
                html=chunk,
                action=context.action,
                error=context.error,
                target_description=(
                    context.target_description
                ),
            )

            try:

                candidates = (
                    self._generate_single_chunk(
                        chunked_context,
                        client,
                    )
                )

                if candidates:

                    logger.info(
                        "HTML chunk %s generated %s candidates.",
                        position + 1,
                        len(candidates),
                    )

                    all_candidates.extend(
                        candidates
                    )

            except Exception as exc:

                logger.warning(
                    "HTML chunk %s failed: %s",
                    position + 1,
                    exc,
                )

        # ========================================================
        # DEDUPLICATE ALL CANDIDATES
        # ========================================================

        unique: dict[
            tuple[str, str],
            LocatorCandidate,
        ] = {}

        for candidate in all_candidates:

            key = (
                candidate.strategy,
                candidate.value,
            )

            existing = unique.get(
                key
            )

            if existing is None:

                unique[key] = candidate

            elif (
                candidate.confidence
                > existing.confidence
            ):

                unique[key] = candidate

        final_candidates = list(
            unique.values()
        )

        # ========================================================
        # SORT
        # ========================================================

        final_candidates.sort(
            key=lambda candidate:
                candidate.confidence,
            reverse=True,
        )

        # ========================================================
        # LIMIT
        # ========================================================

        final_candidates = (
            final_candidates[
                : self.max_candidates
            ]
        )

        logger.info(
            "Final Web locator candidates: %s",
            len(final_candidates),
        )

        for candidate in final_candidates:

            logger.info(
                "Locator candidate: "
                "confidence=%.2f strategy=%s value=%s",
                candidate.confidence,
                candidate.strategy,
                candidate.value,
            )

        return final_candidates

    # ============================================================
    # MAIN
    # ============================================================

    def generate(
        self,
        context: HealingContext,
    ) -> list[LocatorCandidate]:
        """Generate Web locator candidates."""

        client = self.client

        # --------------------------------------------------------
        # Create client lazily.
        # --------------------------------------------------------

        if client is None:

            try:

                from openai import OpenAI

            except Exception as exc:

                raise LLMProviderError(
                    "OpenAI SDK is not installed."
                ) from exc

            kwargs: dict[str, Any] = {}

            if self.api_key:
                kwargs["api_key"] = (
                    self.api_key
                )

            if self.base_url:
                kwargs["base_url"] = (
                    self.base_url
                )

            logger.info(
                "Initializing LLM client. "
                "model=%s base_url=%s",
                self.model,
                self.base_url,
            )

            try:

                client = OpenAI(
                    **kwargs
                )

            except Exception as exc:

                raise LLMProviderError(
                    f"Failed to initialize LLM client: {exc}"
                ) from exc

            self.client = client

        # --------------------------------------------------------
        # Generate candidates.
        # --------------------------------------------------------

        try:

            return self.generate_with_chunking(
                context,
                client,
            )

        except LLMProviderError:

            raise

        except Exception as exc:

            logger.exception(
                "Web locator generator failed."
            )

            raise LLMProviderError(
                str(exc)
            ) from exc
