"""Tests for classifier prompt construction and response parsing."""

import pytest

from dod_scan.classifier_prompt import (
    build_classification_prompt,
    parse_classification_response,
    ClassificationResult,
)


class TestBuildClassificationPrompt:
    def test_prompt_includes_contract_text(self) -> None:
        contract = "Procure 100 laptops for military use"
        prompt = build_classification_prompt(contract)
        assert contract in prompt
        assert "Classify the following DOD contract" in prompt

    def test_prompt_structure(self) -> None:
        contract = "Test contract"
        prompt = build_classification_prompt(contract)
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestParseClassificationResponse:
    def test_valid_json_response(self) -> None:
        response = '{"is_procurement": true, "confidence": 0.95, "reasoning": "It is hardware"}'
        result = parse_classification_response(response)
        assert result is not None
        assert result.is_procurement is True
        assert result.confidence == 0.95
        assert result.reasoning == "It is hardware"

    def test_valid_json_with_extra_text(self) -> None:
        response = (
            'The answer is:\n'
            '{"is_procurement": false, "confidence": 0.8, "reasoning": "Service contract"}'
            '\nDone.'
        )
        result = parse_classification_response(response)
        assert result is not None
        assert result.is_procurement is False
        assert result.confidence == 0.8
        assert result.reasoning == "Service contract"

    def test_missing_is_procurement_field(self) -> None:
        response = '{"confidence": 0.5}'
        result = parse_classification_response(response)
        assert result is None

    def test_no_json_object(self) -> None:
        response = "not json at all"
        result = parse_classification_response(response)
        assert result is None

    def test_invalid_json(self) -> None:
        response = '{"is_procurement": true, "confidence": 0.9, invalid}'
        result = parse_classification_response(response)
        assert result is None

    def test_missing_confidence_uses_default(self) -> None:
        response = '{"is_procurement": true, "reasoning": "Hardware"}'
        result = parse_classification_response(response)
        assert result is not None
        assert result.confidence == 0.5

    def test_missing_reasoning_uses_empty_string(self) -> None:
        response = '{"is_procurement": true, "confidence": 0.9}'
        result = parse_classification_response(response)
        assert result is not None
        assert result.reasoning == ""

    def test_is_procurement_converted_to_bool(self) -> None:
        response_true = '{"is_procurement": 1, "confidence": 0.9, "reasoning": "test"}'
        result_true = parse_classification_response(response_true)
        assert result_true is not None
        assert result_true.is_procurement is True

        response_false = '{"is_procurement": 0, "confidence": 0.9, "reasoning": "test"}'
        result_false = parse_classification_response(response_false)
        assert result_false is not None
        assert result_false.is_procurement is False

    def test_confidence_converted_to_float(self) -> None:
        response = '{"is_procurement": true, "confidence": 1, "reasoning": "test"}'
        result = parse_classification_response(response)
        assert result is not None
        assert isinstance(result.confidence, float)
        assert result.confidence == 1.0

    def test_whitespace_handling(self) -> None:
        response = '   {"is_procurement": true, "confidence": 0.9, "reasoning": "test"}   '
        result = parse_classification_response(response)
        assert result is not None
        assert result.is_procurement is True


class TestClassificationResult:
    def test_frozen_dataclass(self) -> None:
        result = ClassificationResult(
            is_procurement=True,
            confidence=0.95,
            reasoning="It is hardware"
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            result.is_procurement = False

    def test_creation(self) -> None:
        result = ClassificationResult(
            is_procurement=False,
            confidence=0.8,
            reasoning="Service contract"
        )
        assert result.is_procurement is False
        assert result.confidence == 0.8
        assert result.reasoning == "Service contract"
