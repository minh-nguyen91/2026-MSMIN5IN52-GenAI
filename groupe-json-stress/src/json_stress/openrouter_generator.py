
"""OpenRouter-backed JSON generator for the JSON Stress project."""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

try:
    from ..validator import load_schema
except ImportError:
    from validator import load_schema


class OpenRouterGenerator:
    """Generate JSON through the OpenRouter OpenAI-compatible API."""

    provider = "openrouter"

    # Approximate fallback rates in USD per million tokens.
    # These are estimates, not guaranteed prices for every model/provider.
    INPUT_PRICE_PER_MILLION = 0.10
    OUTPUT_PRICE_PER_MILLION = 0.15

    def __init__(self):
        # Load .env from the project root, regardless of the working directory.
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        load_dotenv(os.path.join(project_root, ".env"))

        api_key = os.getenv("MODEL_API_KEY") or os.getenv(
            "OPENROUTER_API_KEY"
        )
        base_url = os.getenv(
            "MODEL_BASE_URL",
            "https://openrouter.ai/api/v1",
        )
        self.model = os.getenv("MODEL_NAME", "qwen/qwen3.5-9b")

        # Keep the output limit configurable through .env.
        self.max_tokens = int(os.getenv("MODEL_MAX_TOKENS", "4096"))

        if self.max_tokens < 1:
            raise ValueError("MODEL_MAX_TOKENS must be at least 1.")

        if not api_key:
            raise ValueError(
                "Missing MODEL_API_KEY. Add your OpenRouter API key "
                "to the local .env file."
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=60.0,
            max_retries=0,
        )

        # Cumulative statistics.
        self.total_cost_usd = 0.0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.estimated_cost_calls = 0
        self.unknown_cost_calls = 0

        # Statistics for the most recent generation attempt.
        self.last_cost_usd = 0.0
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_cost_is_estimate = False
        self.last_cost_status = "unknown"
        self.last_finish_reason = None
        self.last_response_id = None

    def _reset_last_stats(self):
        """Prevent a failed request from reusing previous request stats."""
        self.last_cost_usd = 0.0
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_cost_is_estimate = False
        self.last_cost_status = "unknown"
        self.last_finish_reason = None
        self.last_response_id = None

    def _record_usage(self, usage):
        """Record usage before inspecting response content."""
        prompt_tokens = (
            int(getattr(usage, "prompt_tokens", 0) or 0)
            if usage is not None
            else 0
        )

        completion_tokens = (
            int(getattr(usage, "completion_tokens", 0) or 0)
            if usage is not None
            else 0
        )

        reported_cost = (
            getattr(usage, "cost", None)
            if usage is not None
            else None
        )

        # Some OpenAI-compatible APIs expose extra usage fields only
        # through model_dump(), so check that representation as well.
        if reported_cost is None and usage is not None:
            try:
                usage_data = usage.model_dump(exclude_none=True)
            except Exception:
                usage_data = {}

            reported_cost = usage_data.get("cost")

        self.last_prompt_tokens = prompt_tokens
        self.last_completion_tokens = completion_tokens

        if reported_cost is not None:
            cost = float(reported_cost)
            self.last_cost_is_estimate = False
            self.last_cost_status = "reported"

        elif prompt_tokens > 0 or completion_tokens > 0:
            cost = (
                prompt_tokens * self.INPUT_PRICE_PER_MILLION
                + completion_tokens * self.OUTPUT_PRICE_PER_MILLION
            ) / 1_000_000

            self.last_cost_is_estimate = True
            self.last_cost_status = "estimated"
            self.estimated_cost_calls += 1

        else:
            # Unknown cost is not the same as confirmed zero cost.
            cost = 0.0
            self.last_cost_is_estimate = False
            self.last_cost_status = "unknown"
            self.unknown_cost_calls += 1

        self.last_cost_usd = cost
        self.total_cost_usd += cost
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens

    def _build_prompt(self, schema, feedback):
        """Build a compact prompt while preserving the complete schema."""
        compact_schema = json.dumps(
            schema,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        if feedback:
            feedback_text = json.dumps(
                feedback,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        else:
            feedback_text = "None."

        return f"""
Generate exactly one complete JSON object that satisfies the schema below.

Schema:
{compact_schema}

Previous attempt feedback:
{feedback_text}

Rules:
- Output JSON only. No Markdown, comments, or explanations.
- Include every required property and obey all schema constraints.
- Use the minimum number of array items allowed by the schema.
- Omit optional properties when they are not needed.
- Use short, simple string values.
- Do not add properties that the schema does not allow.
- Follow enum, type, range, format, and conditional constraints.
- Correct all issues mentioned in the previous feedback.
- Keep the entire object compact, but never omit required information.
- Close every string, object, and array correctly.
- Return the complete object, never a partial object or a patch.
""".strip()

    def _response_error_message(self, prefix, partial_length=0):
        """Build a diagnostic message without losing usage statistics."""
        return (
            f"{prefix} "
            f"finish_reason={self.last_finish_reason!r}; "
            f"cost_status={self.last_cost_status!r}; "
            f"last_cost_usd={self.last_cost_usd:.8f}; "
            f"prompt_tokens={self.last_prompt_tokens}; "
            f"completion_tokens={self.last_completion_tokens}; "
            f"partial_chars={partial_length}; "
            f"response_id={self.last_response_id!r}"
        )

    def generate(self, schema_name: str, feedback=None) -> str:
        """Return complete JSON text for the requested schema."""
        self._reset_last_stats()

        schema = load_schema(schema_name)
        prompt = self._build_prompt(schema, feedback)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You generate compact JSON test data. "
                            "Return exactly one complete JSON object. "
                            "Never include Markdown or commentary."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=self.max_tokens,
                # Verified in diagnose_schema3.py:
                # disabling reasoning allows the model to return JSON.
                extra_body={
                    "reasoning": {
                        "enabled": False
                    }
                },
            )

        except Exception:
            # If no response object is returned, actual usage/cost may
            # be unavailable. Do not falsely report confirmed zero cost.
            self.last_cost_status = "unknown"
            self.unknown_cost_calls += 1
            raise

        self.last_response_id = getattr(response, "id", None)

        choices = getattr(response, "choices", None) or []

        if choices:
            choice = choices[0]
            self.last_finish_reason = getattr(
                choice,
                "finish_reason",
                None,
            )
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None)
        else:
            content = None

        # Record usage before raising response-content errors.
        self._record_usage(getattr(response, "usage", None))

        if isinstance(content, str):
            result = content.strip()

        elif isinstance(content, list):
            # Support responses containing text content blocks.
            text_parts = []

            for part in content:
                part_text = (
                    part.get("text")
                    if isinstance(part, dict)
                    else getattr(part, "text", None)
                )

                if part_text:
                    text_parts.append(part_text)

            result = "".join(text_parts).strip()

        else:
            result = ""

        # Never pass a potentially truncated response off as complete JSON.
        if self.last_finish_reason == "length":
            raise RuntimeError(
                self._response_error_message(
                    "The model reached the output token limit; "
                    "the response may be truncated.",
                    partial_length=len(result),
                )
            )

        if not result:
            raise RuntimeError(
                self._response_error_message(
                    "The model returned an empty response.",
                )
            )

        return result
