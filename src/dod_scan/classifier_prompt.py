# pattern: Functional Core
"""Classification prompt construction and response parsing."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a DOD contract classification expert. Your job is to determine "
    "whether a contract is for PROCUREMENT (physical goods, equipment, hardware, "
    "materials, supplies) or SERVICE (labour, maintenance, consulting, IT "
    "services, research services, training, construction services).\n\n"
    "Respond with ONLY a JSON object in this exact format:\n"
    "{\n"
    '  "is_procurement": true,\n'
    '  "confidence": 0.95,\n'
    '  "reasoning": "Brief explanation of why this is procurement or service"\n'
    "}\n\n"
    "Rules:\n"
    '- "is_procurement" must be true (physical goods/hardware) or '
    'false (service/labour)\n'
    '- "confidence" must be a number between 0.0 and 1.0\n'
    '- "reasoning" must be a brief string explaining the classification\n'
    "- Manufacturing, production, and delivery of physical items = procurement\n"
    "- Research, development, maintenance, consulting, training = service\n"
    "- Construction is generally service unless it involves procurement of "
    "equipment/materials as the primary deliverable\n"
    "- If the contract description mentions specific physical items being "
    "procured (vehicles, weapons, equipment, supplies), classify as procurement\n"
    "- If the contract is primarily for labour, expertise, or ongoing services, "
    "classify as service"
)


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
