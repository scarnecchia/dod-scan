# DOD Contract Scanner Implementation Plan — Phase 4

**Goal:** Classify contracts as procurement vs service using configurable LLM provider.

**Architecture:** Provider abstraction with a common interface — Anthropic SDK for direct Claude API, httpx for OpenRouter (OpenAI-compatible endpoint). Classification prompt instructs the model to return structured JSON. Results stored in `classifications` table. Already-classified contracts skipped on re-run.

**Tech Stack:** Python 3.10+, anthropic SDK, httpx, SQLite

**Scope:** 8 phases from original design (phase 4 of 8)

**Codebase verified:** 2026-03-12 — greenfield, Phase 1-3 outputs assumed present

---

## Acceptance Criteria Coverage

This phase implements and tests:

### dod-scan.AC3: LLM classification
- **dod-scan.AC3.1 Success:** Unclassified contracts sent to configured LLM and result stored with classification, confidence, reasoning, model
- **dod-scan.AC3.2 Success:** Already-classified contracts skipped on re-run
- **dod-scan.AC3.3 Success:** OpenRouter provider works with `LLM_PROVIDER=openrouter`
- **dod-scan.AC3.4 Success:** Anthropic provider works with `LLM_PROVIDER=anthropic`
- **dod-scan.AC3.5 Failure:** LLM API error logged to file, classify stage exits non-zero
- **dod-scan.AC3.6 Edge:** Malformed LLM JSON response handled gracefully (logged, contract marked for retry)

---

<!-- START_SUBCOMPONENT_A (tasks 1-3) -->
<!-- START_TASK_1 -->
### Task 1: Classification prompt (Functional Core)

**Verifies:** dod-scan.AC3.1

**Files:**
- Create: `src/dod_scan/classifier_prompt.py`

**Implementation:**

Create `src/dod_scan/classifier_prompt.py` — pure functions for building the classification prompt and parsing the JSON response.

```python
# pattern: Functional Core
"""Classification prompt construction and response parsing."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a DOD contract classification expert. Your job is to determine whether a contract is for PROCUREMENT (physical goods, equipment, hardware, materials, supplies) or SERVICE (labour, maintenance, consulting, IT services, research services, training, construction services).

Respond with ONLY a JSON object in this exact format:
{
  "is_procurement": true,
  "confidence": 0.95,
  "reasoning": "Brief explanation of why this is procurement or service"
}

Rules:
- "is_procurement" must be true (physical goods/hardware) or false (service/labour)
- "confidence" must be a number between 0.0 and 1.0
- "reasoning" must be a brief string explaining the classification
- Manufacturing, production, and delivery of physical items = procurement
- Research, development, maintenance, consulting, training = service
- Construction is generally service unless it involves procurement of equipment/materials as the primary deliverable
- If the contract description mentions specific physical items being procured (vehicles, weapons, equipment, supplies), classify as procurement
- If the contract is primarily for labour, expertise, or ongoing services, classify as service"""


def build_classification_prompt(contract_text: str) -> str:
    return f"Classify the following DOD contract as procurement or service:\n\n{contract_text}"


@dataclass(frozen=True)
class ClassificationResult:
    is_procurement: bool
    confidence: float
    reasoning: str


def parse_classification_response(response_text: str) -> ClassificationResult | None:
    text = response_text.strip()

    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start == -1 or json_end == 0:
        logger.warning("No JSON object found in LLM response: %s", text[:200])
        return None

    try:
        data = json.loads(text[json_start:json_end])
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON from LLM response: %s", text[:200])
        return None

    if "is_procurement" not in data:
        logger.warning("Missing 'is_procurement' in LLM response: %s", data)
        return None

    return ClassificationResult(
        is_procurement=bool(data["is_procurement"]),
        confidence=float(data.get("confidence", 0.5)),
        reasoning=str(data.get("reasoning", "")),
    )
```

**Commit:** `feat: add classification prompt and response parsing`
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: LLM provider implementations (Imperative Shell)

**Verifies:** dod-scan.AC3.3, dod-scan.AC3.4, dod-scan.AC3.5

**Files:**
- Create: `src/dod_scan/classifier_providers.py`

**Implementation:**

Create `src/dod_scan/classifier_providers.py` — provider abstraction with Anthropic and OpenRouter implementations.

```python
# pattern: Imperative Shell
"""LLM provider implementations for contract classification."""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from dod_scan.classifier_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    def classify(self, user_prompt: str) -> str:
        """Send classification prompt and return raw response text."""
        ...

    @property
    def model_name(self) -> str: ...


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def classify(self, user_prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.0,
        )
        return response.content[0].text


class OpenRouterProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._url = "https://openrouter.ai/api/v1/chat/completions"

    @property
    def model_name(self) -> str:
        return self._model

    def classify(self, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 512,
            "temperature": 0.0,
        }
        resp = httpx.post(
            self._url, json=payload, headers=headers, timeout=60.0
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def create_provider(provider: str, api_key: str, model: str) -> LLMProvider:
    if provider == "anthropic":
        return AnthropicProvider(api_key, model)
    if provider == "openrouter":
        return OpenRouterProvider(api_key, model)
    raise ValueError(f"Unknown LLM provider: {provider}")
```

**Commit:** `feat: add Anthropic and OpenRouter LLM provider implementations`
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: Classifier tests

**Verifies:** dod-scan.AC3.1, dod-scan.AC3.3, dod-scan.AC3.4, dod-scan.AC3.5, dod-scan.AC3.6

**Files:**
- Create: `tests/test_classifier_prompt.py`
- Create: `tests/test_classifier_providers.py`

**Testing:**

Tests must verify each AC listed above:

- dod-scan.AC3.1: `build_classification_prompt` includes the contract text. `parse_classification_response` extracts is_procurement, confidence, reasoning from valid JSON response.

- dod-scan.AC3.3: `OpenRouterProvider.classify` sends correct POST request to `https://openrouter.ai/api/v1/chat/completions` with correct headers and payload format. Mock httpx.post to return a valid OpenRouter response. Verify the response text is extracted from `choices[0].message.content`.

- dod-scan.AC3.4: `AnthropicProvider.classify` calls `client.messages.create` with correct model, system prompt, and user message. Mock the Anthropic client to return a response. Verify text is extracted from `response.content[0].text`.

- dod-scan.AC3.5: When httpx.post raises `httpx.HTTPStatusError` (OpenRouter) or Anthropic raises `APIError`, the exception propagates. Test that provider.classify raises on API failure.

- dod-scan.AC3.6: `parse_classification_response` with malformed JSON (missing braces, invalid JSON, missing is_procurement field) returns None. Test with: `"not json at all"`, `'{"confidence": 0.5}'` (missing is_procurement), `'{"is_procurement": true, "confidence": 0.9, "reasoning": "It is hardware"}'` (valid).

- `create_provider` returns correct provider type for "anthropic" and "openrouter", raises ValueError for unknown.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_classifier_prompt.py tests/test_classifier_providers.py -v`
Expected: All tests pass

**Commit:** `test: add classifier prompt and provider tests`
<!-- END_TASK_3 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_SUBCOMPONENT_B (tasks 4-5) -->
<!-- START_TASK_4 -->
### Task 4: Classifier orchestration and DB persistence

**Verifies:** dod-scan.AC3.1, dod-scan.AC3.2, dod-scan.AC3.6

**Files:**
- Create: `src/dod_scan/classifier.py`

**Implementation:**

Create `src/dod_scan/classifier.py` — orchestration module that reads unclassified contracts, sends to LLM, and stores results.

```python
# pattern: Imperative Shell
"""Classifier orchestration — sends contracts to LLM and stores classifications."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from dod_scan.classifier_prompt import (
    build_classification_prompt,
    parse_classification_response,
)
from dod_scan.classifier_providers import LLMProvider

logger = logging.getLogger(__name__)


def classify_all(conn: sqlite3.Connection, provider: LLMProvider) -> int:
    unclassified = conn.execute(
        """
        SELECT id, raw_text FROM contracts
        WHERE id NOT IN (SELECT contract_id FROM classifications)
        """
    ).fetchall()

    classified_count = 0

    for row in unclassified:
        contract_id = row["id"]
        raw_text = row["raw_text"]

        prompt = build_classification_prompt(raw_text)

        try:
            response_text = provider.classify(prompt)
        except Exception:
            logger.exception("LLM API error for contract %d", contract_id)
            raise

        result = parse_classification_response(response_text)
        if result is None:
            logger.warning(
                "Malformed LLM response for contract %d, skipping (will retry next run)",
                contract_id,
            )
            continue

        conn.execute(
            """
            INSERT INTO classifications (
                contract_id, is_procurement, confidence, reasoning,
                model_used, classified_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                contract_id,
                result.is_procurement,
                result.confidence,
                result.reasoning,
                provider.model_name,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        classified_count += 1
        logger.info(
            "Classified contract %d: procurement=%s confidence=%.2f",
            contract_id,
            result.is_procurement,
            result.confidence,
        )

    logger.info("Classification complete: %d contracts classified", classified_count)
    return classified_count
```

**Commit:** `feat: add classifier orchestration with DB persistence`
<!-- END_TASK_4 -->

<!-- START_TASK_5 -->
### Task 5: Classifier orchestration tests

**Verifies:** dod-scan.AC3.1, dod-scan.AC3.2, dod-scan.AC3.6

**Files:**
- Create: `tests/test_classifier_orchestration.py`

**Testing:**

Tests must verify the orchestration layer against the DB:

- dod-scan.AC3.1: Insert contract rows into DB. Create a mock LLMProvider that returns valid JSON classification. Call `classify_all()`. Verify `classifications` table has rows with correct is_procurement, confidence, reasoning, model_used.

- dod-scan.AC3.2: Insert contract + classification rows. Call `classify_all()`. Verify mock provider was NOT called for the already-classified contract. Only unclassified contracts trigger LLM calls.

- dod-scan.AC3.6: Mock provider returns malformed JSON for one contract. Verify that contract is skipped (no classification row inserted), but other contracts are still classified. The malformed contract can be retried on next run (no classification row blocks it).

Use `tmp_db` and `db_conn` fixtures. Create a simple mock provider class implementing the LLMProvider protocol.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_classifier_orchestration.py -v`
Expected: All tests pass

**Commit:** `test: add classifier orchestration tests`
<!-- END_TASK_5 -->
<!-- END_SUBCOMPONENT_B -->

<!-- START_TASK_6 -->
### Task 6: Wire classify subcommand in CLI

**Files:**
- Modify: `src/dod_scan/cli.py` — replace `classify` stub with real implementation

**Implementation:**

Update the `classify` command in `cli.py`:

```python
@app.command()
def classify() -> None:
    """Classify contracts as procurement vs service using LLM."""
    settings = get_settings()
    if not settings.llm_api_key:
        typer.echo("Error: LLM_API_KEY not set. Configure in .env file.", err=True)
        raise typer.Exit(code=1)

    init_db(settings.database_path)
    conn = get_connection(settings.database_path)
    try:
        from dod_scan.classifier import classify_all
        from dod_scan.classifier_providers import create_provider

        provider = create_provider(
            settings.llm_provider, settings.llm_api_key, settings.llm_model
        )
        count = classify_all(conn, provider)
        typer.echo(f"Classification complete: {count} contracts classified")
    except Exception as exc:
        typer.echo(f"Classification failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()
```

**Verification:**
Run: `dod-scan classify --help`
Expected: Shows help text

**Commit:** `feat: wire classify subcommand to classifier orchestration`
<!-- END_TASK_6 -->
