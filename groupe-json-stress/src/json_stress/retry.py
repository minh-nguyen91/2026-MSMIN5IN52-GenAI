
"""
JSON Stress project: retry and recovery strategy.

Generate JSON, parse it, validate it against a schema, and retry
when generation, parsing, or validation fails.
"""

from __future__ import annotations

import json
import time
from typing import Any

try:
    # Support imports from src.json_stress.retry
    from ..validator import validate_json
except ImportError:
    # Support adding the src directory to the Python module search path
    from validator import validate_json


class RetryManager:
    """Run JSON generation with a bounded number of attempts."""

    def __init__(
        self,
        max_attempts: int = 3,
        max_latency_ms: float | None = None,
        max_cost: float | None = None,
        cost_per_attempt: float = 0.0,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if max_latency_ms is not None and max_latency_ms < 0:
            raise ValueError("max_latency_ms cannot be negative.")
        if max_cost is not None and max_cost < 0:
            raise ValueError("max_cost cannot be negative.")
        if cost_per_attempt < 0:
            raise ValueError("cost_per_attempt cannot be negative.")

        self.max_attempts = max_attempts
        self.max_latency_ms = max_latency_ms
        self.max_cost = max_cost
        self.cost_per_attempt = cost_per_attempt

    @staticmethod
    def _is_output_truncated(errors: list[dict]) -> bool:
        """
        Detect errors indicating that the model reached its output token limit.

        The OpenRouter generator includes finish_reason='length' in its
        exception message when the response is truncated or empty.
        """
        for error in errors:
            message = str(error.get("message", "")).lower()

            if "finish_reason" in message and "length" in message:
                return True

        return False

    @staticmethod
    def _build_retry_feedback(errors: list[dict]) -> list[dict]:
        """Build feedback for the next generation attempt."""
        feedback = list(errors)

        if RetryManager._is_output_truncated(errors):
            feedback.append(
                {
                    "path": "$",
                    "type": "output_truncated",
                    "message": (
                        "The previous response reached the output token "
                        "limit and may have been truncated. On this attempt, "
                        "generate a compact but complete JSON object that "
                        "satisfies the entire schema. Use the minimum number "
                        "of array items allowed by the schema, omit optional "
                        "fields when possible, keep strings concise, and "
                        "ensure all JSON objects, arrays, and strings are "
                        "properly closed. Do not include explanations or "
                        "Markdown fences."
                    ),
                }
            )

        return feedback

    def run(self, generator: Any, schema_name: str) -> dict:
        """Generate, parse, validate, and retry when necessary."""

        start_time = time.perf_counter()
        history: list[dict] = []
        feedback: list[dict] = []

        first_try_valid = False
        final_valid = False
        final_data = None
        final_raw = None
        final_errors: list[dict] = []
        error_type = None
        attempts = 0
        stop_reason = None

        provider = getattr(generator, "provider", "unknown")
        model = getattr(generator, "model", "unknown")

        for attempt_number in range(1, self.max_attempts + 1):
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Stop before making another API call if the latency limit
            # has already been reached.
            if (
                self.max_latency_ms is not None
                and elapsed_ms >= self.max_latency_ms
            ):
                stop_reason = "latency_limit"
                break

            # This is a configured cost estimate, not actual API billing.
            next_cost = (attempts + 1) * self.cost_per_attempt

            if self.max_cost is not None and next_cost > self.max_cost:
                stop_reason = "cost_limit"
                break

            attempts += 1
            attempt_started = time.perf_counter()

            raw_output = None
            parsed_data = None
            errors: list[dict] = []
            attempt_error_type = None

            # Step 1: Generate the response.
            try:
                raw_output = generator.generate(
                    schema_name,
                    feedback=feedback,
                )
            except Exception as exc:
                attempt_valid = False
                attempt_error_type = "generation_error"

                errors = [
                    {
                        "path": "$",
                        "message": str(exc),
                        "type": attempt_error_type,
                    }
                ]

            else:
                # Step 2: Parse the generated JSON.
                try:
                    parsed_data = json.loads(raw_output)

                except (json.JSONDecodeError, TypeError) as exc:
                    attempt_valid = False
                    attempt_error_type = "json_parse_error"

                    errors = [
                        {
                            "path": "$",
                            "message": str(exc),
                            "type": attempt_error_type,
                        }
                    ]

                else:
                    # Step 3: Validate the parsed JSON against the schema.
                    try:
                        validation = validate_json(
                            parsed_data,
                            schema_name,
                        )

                    except Exception as exc:
                        attempt_valid = False
                        attempt_error_type = "validation_error"

                        errors = [
                            {
                                "path": "$",
                                "message": str(exc),
                                "type": attempt_error_type,
                            }
                        ]

                    else:
                        attempt_valid = validation["valid"]

                        if not attempt_valid:
                            errors = validation.get("errors", [])

                            attempt_error_type = (
                                errors[0].get(
                                    "type",
                                    "validation_error",
                                )
                                if errors
                                else "validation_error"
                            )

            attempt_latency_ms = (
                time.perf_counter() - attempt_started
            ) * 1000

            if attempt_number == 1:
                first_try_valid = attempt_valid

            # Record every attempt for later analysis.
            history.append(
                {
                    "attempt": attempt_number,
                    "raw_output": raw_output,
                    "valid": attempt_valid,
                    "errors": errors,
                    "error_type": attempt_error_type,
                    "latency_ms": round(attempt_latency_ms, 3),
                }
            )

            final_raw = raw_output
            final_data = parsed_data
            final_valid = attempt_valid
            final_errors = errors
            error_type = attempt_error_type

            # Stop immediately when a valid JSON object is obtained.
            if attempt_valid:
                error_type = None
                break

            # Build feedback for the next attempt. If the previous
            # response was truncated, include specific recovery guidance.
            feedback = self._build_retry_feedback(errors)

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Do not start another attempt after the latency budget
            # has been exhausted.
            if (
                self.max_latency_ms is not None
                and elapsed_ms >= self.max_latency_ms
            ):
                stop_reason = "latency_limit"
                break

        total_latency_ms = (time.perf_counter() - start_time) * 1000

        # Keep the existing estimated-cost behavior.
        # Actual API costs are collected by the experiment runner.
        total_cost = attempts * self.cost_per_attempt

        if stop_reason is None:
            if final_valid:
                stop_reason = "success"
            elif attempts >= self.max_attempts:
                stop_reason = "max_attempts_reached"
            elif attempts == 0:
                stop_reason = "no_attempts"
            else:
                stop_reason = "stopped"

        return {
            "schema_id": schema_name,
            "strategy": "retry",
            "first_try_valid": first_try_valid,
            "final_valid": final_valid,
            "attempts": attempts,
            "latency_ms": round(total_latency_ms, 3),
            "cost": round(total_cost, 6),
            "error_type": error_type,
            "provider": provider,
            "model": model,
            "data": final_data,
            "raw_output": final_raw,
            "errors": final_errors,
            "history": history,
            "stop_reason": stop_reason,
        }
