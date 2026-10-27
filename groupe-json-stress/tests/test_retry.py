
"""Tests for the JSON generation retry strategy."""

import sys
from pathlib import Path

import pytest

# Make the project's src directory importable when running pytest.
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from json_stress.generator import MockGenerator
from json_stress.retry import RetryManager


def test_retry_succeeds_on_second_attempt():
    """A failed first response should be retried successfully."""
    generator = MockGenerator(
        scripted_outputs={
            "schema_01.json": [
                '{"name": "Alice"}',
                '{"name": "Alice", "age": 23}',
            ]
        }
    )

    result = RetryManager(max_attempts=3).run(
        generator, "schema_01.json"
    )

    assert result["first_try_valid"] is False
    assert result["final_valid"] is True
    assert result["attempts"] == 2
    assert generator.calls == 2
    assert result["data"] == {"name": "Alice", "age": 23}
    assert result["error_type"] is None
    assert result["stop_reason"] == "success"
    assert len(result["history"]) == 2


def test_retry_stops_after_max_attempts():
    """Repeated schema validation failures must stop at the limit."""
    generator = MockGenerator(
        scripted_outputs={
            "schema_01.json": [
                '{"name": "Alice"}',
                '{"name": "Bob"}',
                '{"name": "Charlie"}',
            ]
        }
    )

    result = RetryManager(max_attempts=3).run(
        generator, "schema_01.json"
    )

    assert result["final_valid"] is False
    assert result["attempts"] == 3
    assert generator.calls == 3
    assert result["error_type"] == "missing_required_field"
    assert result["stop_reason"] == "max_attempts_reached"
    assert len(result["history"]) == 3


def test_invalid_json_is_recorded_and_retried():
    """Malformed JSON should be classified as a parsing error."""
    generator = MockGenerator(
        scripted_outputs={
            "schema_01.json": [
                '{"name": "Alice", "age": ',
                '{"name": "Alice", "age": 23}',
            ]
        }
    )

    result = RetryManager(max_attempts=3).run(
        generator, "schema_01.json"
    )

    assert result["first_try_valid"] is False
    assert result["final_valid"] is True
    assert result["attempts"] == 2
    assert result["history"][0]["error_type"] == "json_parse_error"
    assert result["stop_reason"] == "success"


def test_generator_exception_is_recorded_and_retried():
    """A transient generator failure should not crash the retry loop."""

    class SometimesFailingGenerator:
        provider = "test"
        model = "sometimes-failing"

        def __init__(self):
            self.calls = 0

        def generate(self, schema_name, feedback=None):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Temporary service failure")
            return '{"name": "Alice", "age": 23}'

    generator = SometimesFailingGenerator()

    result = RetryManager(max_attempts=3).run(
        generator, "schema_01.json"
    )

    assert result["first_try_valid"] is False
    assert result["final_valid"] is True
    assert result["attempts"] == 2
    assert generator.calls == 2
    assert result["history"][0]["error_type"] == "generation_error"
    assert result["stop_reason"] == "success"


def test_metrics_are_recorded():
    """The result should contain the fields expected by evaluation.py."""
    generator = MockGenerator()

    result = RetryManager(
        max_attempts=3,
        cost_per_attempt=0.01,
    ).run(generator, "schema_01.json")

    expected_fields = {
        "schema_id",
        "strategy",
        "first_try_valid",
        "final_valid",
        "attempts",
        "latency_ms",
        "cost",
        "error_type",
        "provider",
        "model",
    }

    assert expected_fields.issubset(result.keys())
    assert result["final_valid"] is True
    assert result["attempts"] == 1
    assert result["latency_ms"] >= 0
    assert result["cost"] == pytest.approx(0.01)
    assert result["provider"] == "mock"
    assert result["model"] == "mock-v1"
    assert len(result["history"]) == 1


def test_max_attempts_must_be_positive():
    """Zero or negative attempt limits should be rejected."""
    with pytest.raises(ValueError, match="max_attempts"):
        RetryManager(max_attempts=0)


def test_cost_limit_prevents_generation():
    """The manager should not exceed the configured cost budget."""
    generator = MockGenerator()

    result = RetryManager(
        max_attempts=3,
        max_cost=0.01,
        cost_per_attempt=0.01,
    ).run(generator, "schema_01.json")

    assert result["attempts"] == 1
    assert generator.calls == 1
    assert result["final_valid"] is True
    assert result["cost"] == pytest.approx(0.01)


def test_zero_latency_budget_prevents_generation():
    """A zero time budget should stop before the first attempt."""
    generator = MockGenerator()

    result = RetryManager(
        max_attempts=3,
        max_latency_ms=0,
    ).run(generator, "schema_01.json")

    assert result["attempts"] == 0
    assert generator.calls == 0
    assert result["final_valid"] is False
    assert result["stop_reason"] == "latency_limit"
