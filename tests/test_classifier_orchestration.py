"""Tests for classifier orchestration."""

import sqlite3

import pytest

from dod_scan.classifier import classify_all


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(
        self, responses: dict[int, str | None], model: str = "test-model"
    ) -> None:
        self._responses = responses
        self._model = model
        self.call_count = 0

    @property
    def model_name(self) -> str:
        return self._model

    def classify(self, user_prompt: str) -> str:
        self.call_count += 1
        # Extract contract ID from the prompt (it's embedded in the contract text)
        # For testing, we'll match the call order
        contract_id = list(self._responses.keys())[self.call_count - 1]
        response = self._responses.get(contract_id)
        if response is None:
            raise ValueError(f"No response configured for call {self.call_count}")
        return response


class TestClassifyAll:
    def test_classify_unclassified_contracts(self, db_conn: sqlite3.Connection) -> None:
        """Test dod-scan.AC3.1: Unclassified contracts are sent to LLM and stored."""
        db_conn.execute(
            """
            INSERT INTO contracts (id, raw_text)
            VALUES (1, 'Procure 100 laptops for military use')
            """
        )
        db_conn.commit()

        mock_provider = MockLLMProvider(
            {
                1: '{"is_procurement": true, "confidence": 0.95, "reasoning": "Physical goods"}'
            }
        )

        result = classify_all(db_conn, mock_provider)

        assert result == 1
        assert mock_provider.call_count == 1

        # Verify the classification was stored
        row = db_conn.execute(
            "SELECT * FROM classifications WHERE contract_id = 1"
        ).fetchone()
        assert row is not None
        assert row["is_procurement"] == 1  # True
        assert row["confidence"] == 0.95
        assert row["reasoning"] == "Physical goods"
        assert row["model_used"] == "test-model"

    def test_skip_already_classified_contracts(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Test dod-scan.AC3.2: Already-classified contracts are skipped."""
        # Insert a contract and its classification
        db_conn.execute(
            """
            INSERT INTO contracts (id, raw_text)
            VALUES (1, 'Procure equipment')
            """
        )
        db_conn.execute(
            """
            INSERT INTO classifications (
                contract_id, is_procurement, confidence, reasoning, model_used
            ) VALUES (1, 1, 0.9, 'Existing classification', 'old-model')
            """
        )
        db_conn.commit()

        # Insert an unclassified contract
        db_conn.execute(
            """
            INSERT INTO contracts (id, raw_text)
            VALUES (2, 'Consulting services')
            """
        )
        db_conn.commit()

        mock_provider = MockLLMProvider(
            {2: '{"is_procurement": false, "confidence": 0.8, "reasoning": "Service"}'}
        )

        result = classify_all(db_conn, mock_provider)

        # Only the unclassified contract should be processed
        assert result == 1
        assert mock_provider.call_count == 1

        # Verify the existing classification is unchanged
        row = db_conn.execute(
            "SELECT * FROM classifications WHERE contract_id = 1"
        ).fetchone()
        assert row["model_used"] == "old-model"

    def test_malformed_json_response_skipped(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Test dod-scan.AC3.6: Malformed JSON responses are skipped gracefully."""
        db_conn.execute(
            """
            INSERT INTO contracts (id, raw_text)
            VALUES (1, 'Bad response contract'), (2, 'Good response contract')
            """
        )
        db_conn.commit()

        mock_provider = MockLLMProvider(
            {
                1: "This is not valid JSON at all",
                2: '{"is_procurement": true, "confidence": 0.9, "reasoning": "Works"}',
            }
        )

        result = classify_all(db_conn, mock_provider)

        # Only the contract with valid JSON should be classified
        assert result == 1
        assert mock_provider.call_count == 2

        # First contract should have no classification row
        row = db_conn.execute(
            "SELECT * FROM classifications WHERE contract_id = 1"
        ).fetchone()
        assert row is None

        # Second contract should have a classification row
        row = db_conn.execute(
            "SELECT * FROM classifications WHERE contract_id = 2"
        ).fetchone()
        assert row is not None
        assert row["is_procurement"] == 1

    def test_multiple_contracts_classified(self, db_conn: sqlite3.Connection) -> None:
        """Test classifying multiple contracts in one run."""
        db_conn.execute(
            """
            INSERT INTO contracts (id, raw_text)
            VALUES
                (1, 'Procure tanks'),
                (2, 'Maintenance contract'),
                (3, 'Supply ammunition')
            """
        )
        db_conn.commit()

        mock_provider = MockLLMProvider(
            {
                1: '{"is_procurement": true, "confidence": 0.95, "reasoning": "Equipment"}',
                2: '{"is_procurement": false, "confidence": 0.85, "reasoning": "Service"}',
                3: '{"is_procurement": true, "confidence": 0.9, "reasoning": "Supplies"}',
            }
        )

        result = classify_all(db_conn, mock_provider)

        assert result == 3
        assert mock_provider.call_count == 3

        # Verify all classifications were stored
        row1 = db_conn.execute(
            "SELECT * FROM classifications WHERE contract_id = 1"
        ).fetchone()
        assert row1["is_procurement"] == 1

        row2 = db_conn.execute(
            "SELECT * FROM classifications WHERE contract_id = 2"
        ).fetchone()
        assert row2["is_procurement"] == 0

        row3 = db_conn.execute(
            "SELECT * FROM classifications WHERE contract_id = 3"
        ).fetchone()
        assert row3["is_procurement"] == 1

    def test_no_contracts_to_classify(self, db_conn: sqlite3.Connection) -> None:
        """Test when there are no unclassified contracts."""
        mock_provider = MockLLMProvider({})

        result = classify_all(db_conn, mock_provider)

        assert result == 0
        assert mock_provider.call_count == 0

    def test_mixed_valid_and_invalid_responses(
        self, db_conn: sqlite3.Connection,
    ) -> None:
        """Test handling of mixed valid and invalid responses."""
        db_conn.execute(
            """
            INSERT INTO contracts (id, raw_text)
            VALUES (1, 'Contract 1'), (2, 'Contract 2'), (3, 'Contract 3'), (4, 'Contract 4')
            """
        )
        db_conn.commit()

        mock_provider = MockLLMProvider(
            {
                1: '{"is_procurement": true, "confidence": 0.9, "reasoning": "Good"}',
                2: 'Invalid response',
                3: '{"confidence": 0.8}',  # Missing is_procurement
                4: '{"is_procurement": false, "confidence": 0.7, "reasoning": "Good"}',
            }
        )

        result = classify_all(db_conn, mock_provider)

        # Only contracts 1 and 4 should be classified
        assert result == 2
        assert mock_provider.call_count == 4

        # Verify the correct contracts were classified
        classified_ids = db_conn.execute(
            "SELECT contract_id FROM classifications ORDER BY contract_id"
        ).fetchall()
        assert len(classified_ids) == 2
        assert classified_ids[0]["contract_id"] == 1
        assert classified_ids[1]["contract_id"] == 4

    def test_api_error_propagates(self, db_conn: sqlite3.Connection) -> None:
        """Test that API errors propagate and stop classification."""
        db_conn.execute(
            """
            INSERT INTO contracts (id, raw_text)
            VALUES (1, 'Contract 1'), (2, 'Contract 2')
            """
        )
        db_conn.commit()

        # Create a provider that raises on the first call
        class FailingProvider:
            @property
            def model_name(self) -> str:
                return "failing-model"

            def classify(self, user_prompt: str) -> str:
                raise RuntimeError("API connection failed")

        provider = FailingProvider()

        with pytest.raises(RuntimeError, match="API connection failed"):
            classify_all(db_conn, provider)

    def test_classification_stored_with_correct_timestamp(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Test that classifications are stored with proper timestamps."""
        db_conn.execute(
            """
            INSERT INTO contracts (id, raw_text)
            VALUES (1, 'Test contract')
            """
        )
        db_conn.commit()

        mock_provider = MockLLMProvider(
            {1: '{"is_procurement": true, "confidence": 0.9, "reasoning": "Test"}'}
        )

        classify_all(db_conn, mock_provider)

        row = db_conn.execute(
            "SELECT classified_at FROM classifications WHERE contract_id = 1"
        ).fetchone()
        assert row["classified_at"] is not None
        # Check it's a valid ISO format timestamp
        assert "T" in row["classified_at"]
        assert "Z" in row["classified_at"] or "+" in row["classified_at"]

    def test_confidence_stored_as_float(self, db_conn: sqlite3.Connection) -> None:
        """Test that confidence values are stored as floats."""
        db_conn.execute(
            """
            INSERT INTO contracts (id, raw_text)
            VALUES (1, 'Test contract')
            """
        )
        db_conn.commit()

        mock_provider = MockLLMProvider(
            {1: '{"is_procurement": true, "confidence": 0.75, "reasoning": "Test"}'}
        )

        classify_all(db_conn, mock_provider)

        row = db_conn.execute(
            "SELECT confidence FROM classifications WHERE contract_id = 1"
        ).fetchone()
        assert isinstance(row["confidence"], float)
        assert row["confidence"] == 0.75
