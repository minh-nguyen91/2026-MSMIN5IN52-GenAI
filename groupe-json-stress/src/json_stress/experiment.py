
"""Run baseline and retry experiments with OpenRouter."""

import argparse
import json
import time
from pathlib import Path

from json_stress.openrouter_generator import OpenRouterGenerator
from json_stress.retry import RetryManager
from validator import validate_json


SCHEMA_NAMES = [f"schema_{i:02d}.json" for i in range(1, 6)]


def write_record(file_handle, record):
    """Write one JSONL record and flush it immediately."""
    file_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    file_handle.flush()


def take_usage_snapshot(generator):
    """Capture cumulative generator statistics before an experiment."""
    return {
        "cost": generator.total_cost_usd,
        "prompt_tokens": generator.total_prompt_tokens,
        "completion_tokens": generator.total_completion_tokens,
        "estimated_calls": generator.estimated_cost_calls,
        "unknown_calls": getattr(generator, "unknown_cost_calls", 0),
    }


def get_usage_delta(generator, before):
    """Return usage accumulated since the snapshot."""
    cost = generator.total_cost_usd - before["cost"]
    prompt_tokens = (
        generator.total_prompt_tokens - before["prompt_tokens"]
    )
    completion_tokens = (
        generator.total_completion_tokens - before["completion_tokens"]
    )
    estimated_calls = (
        generator.estimated_cost_calls - before["estimated_calls"]
    )
    unknown_calls = (
        getattr(generator, "unknown_cost_calls", 0)
        - before["unknown_calls"]
    )

    if unknown_calls > 0:
        if estimated_calls > 0:
            cost_status = "mixed_with_unknown"
        else:
            cost_status = "unknown"
    elif estimated_calls > 0:
        cost_status = "estimated"
    else:
        last_status = getattr(generator, "last_cost_status", "unknown")
        cost_status = (
            "reported"
            if last_status == "reported"
            else "unknown"
        )

    return {
        "cost": round(max(0.0, cost), 10),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_calls": estimated_calls,
        "unknown_calls": unknown_calls,
        "cost_status": cost_status,
        "cost_is_estimate": estimated_calls > 0,
    }


def run_one(generator, schema_name, strategy, max_attempts):
    """Run one baseline or retry experiment and return its result."""
    before = take_usage_snapshot(generator)

    attempts_limit = 1 if strategy == "baseline" else max_attempts

    manager = RetryManager(
        max_attempts=attempts_limit,
        cost_per_attempt=0.0,
    )

    try:
        result = manager.run(generator, schema_name)
    except Exception as exc:
        usage = get_usage_delta(generator, before)
        return {
            "schema_id": schema_name,
            "strategy": strategy,
            "first_try_valid": False,
            "final_valid": False,
            "attempts": 0,
            "error_type": "experiment_error",
            "data": None,
            "raw_output": None,
            "errors": [{"message": str(exc)}],
            "history": [],
            "stop_reason": "experiment_error",
            **usage,
        }

    # Use the generator's actual tracked usage, including failed attempts.
    usage = get_usage_delta(generator, before)
    result.update(usage)

    result["strategy"] = strategy
    result["provider"] = generator.provider
    result["model"] = generator.model

    return result


def check_connection(generator):
    """Make one API call before starting a larger experiment."""
    before = take_usage_snapshot(generator)

    print(f"Testing model: {generator.model}")

    try:
        raw = generator.generate("schema_01.json")
    except Exception as exc:
        usage = get_usage_delta(generator, before)
        print("\nThe API request failed.")
        print(f"Error: {exc}")
        print(f"Cost status: {usage['cost_status']}")
        print(f"Cost recorded: ${usage['cost']:.8f}")
        print(f"Prompt tokens: {usage['prompt_tokens']}")
        print(f"Completion tokens: {usage['completion_tokens']}")
        raise

    print("\nRaw response:")
    print(raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"The model response is not valid JSON: {exc}"
        ) from exc

    validation = validate_json(data, "schema_01.json")
    usage = get_usage_delta(generator, before)

    print("\nValidation result:")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    print(f"\nCost recorded: ${usage['cost']:.8f}")
    print(f"Cost status: {usage['cost_status']}")
    print(f"Prompt tokens: {usage['prompt_tokens']}")
    print(f"Completion tokens: {usage['completion_tokens']}")


def run_experiments(args):
    generator = OpenRouterGenerator()

    if args.check_only:
        check_connection(generator)
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Protect existing result files from accidental replacement.
    if output_path.exists() and not args.overwrite_output:
        raise FileExistsError(
            f"Output file already exists: {output_path}\n"
            "Choose a different --output path, or add "
            "--overwrite-output if you intentionally want to replace it."
        )

    schema_names = (
        [args.only_schema]
        if args.only_schema
        else SCHEMA_NAMES
    )

    sample_start = args.start_sample
    sample_end = sample_start + args.runs_per_schema - 1

    print(f"Schemas: {', '.join(schema_names)}")
    print(f"Samples per schema: {args.runs_per_schema}")
    print(f"Sample range: {sample_start:03d}-{sample_end:03d}")
    print(f"Maximum attempts: {args.max_attempts}")
    print(f"Current-run cost limit: ${args.max_total_cost_usd:.6f}")
    print(f"Output file: {output_path}")

    total_records = 0
    stopped_for_budget = False

    # Each run creates a new output file, but never silently overwrites one.
    with output_path.open("w", encoding="utf-8") as output_file:
        for schema_name in schema_names:
            for sample_number in range(
                sample_start,
                sample_start + args.runs_per_schema,
            ):
                sample_id = f"{schema_name}-sample-{sample_number:03d}"

                for strategy in ("baseline", "retry"):
                    # Do not start a new strategy after reaching the budget.
                    if (
                        generator.total_cost_usd
                        >= args.max_total_cost_usd
                    ):
                        stopped_for_budget = True
                        break

                    started = time.perf_counter()
                    before = take_usage_snapshot(generator)

                    try:
                        result = run_one(
                            generator,
                            schema_name,
                            strategy,
                            args.max_attempts,
                        )
                    except Exception as exc:
                        usage = get_usage_delta(generator, before)
                        result = {
                            "schema_id": schema_name,
                            "strategy": strategy,
                            "first_try_valid": False,
                            "final_valid": False,
                            "attempts": 0,
                            "error_type": "experiment_error",
                            "data": None,
                            "raw_output": None,
                            "errors": [{"message": str(exc)}],
                            "history": [],
                            "stop_reason": "experiment_error",
                            **usage,
                        }

                    result["sample_id"] = sample_id
                    result["provider"] = generator.provider
                    result["model"] = generator.model
                    result["latency_ms"] = (
                        time.perf_counter() - started
                    ) * 1000

                    # Normalize older or incomplete result records.
                    result.setdefault("cost", 0.0)
                    result.setdefault("cost_status", "unknown")
                    result.setdefault("cost_is_estimate", False)
                    result.setdefault("prompt_tokens", 0)
                    result.setdefault("completion_tokens", 0)
                    result["cost"] = round(
                        float(result.get("cost", 0.0)), 10
                    )

                    write_record(output_file, result)
                    total_records += 1

                    print(
                        f"[{total_records}] {sample_id} | {strategy} | "
                        f"valid={result.get('final_valid')} | "
                        f"attempts={result.get('attempts')} | "
                        f"cost=${result['cost']:.8f} | "
                        f"cost_status={result.get('cost_status')}"
                    )

                    # The current record is flushed before this check.
                    if (
                        generator.total_cost_usd
                        >= args.max_total_cost_usd
                    ):
                        stopped_for_budget = True
                        break

                if stopped_for_budget:
                    break

            if stopped_for_budget:
                break

    print("\nExperiment finished.")
    print(f"Output file: {output_path}")
    print(f"Records written: {total_records}")
    print(
        "Reported/estimated cost total for this run: "
        f"${generator.total_cost_usd:.6f}"
    )
    print(f"Prompt tokens: {generator.total_prompt_tokens}")
    print(f"Completion tokens: {generator.total_completion_tokens}")
    print(
        "Calls with estimated cost: "
        f"{generator.estimated_cost_calls}"
    )
    print(
        "Calls with unknown cost: "
        f"{getattr(generator, 'unknown_cost_calls', 0)}"
    )

    if stopped_for_budget:
        print(
            "Stopped after reaching the configured cost threshold. "
            "The final request may have crossed the threshold."
        )

    if getattr(generator, "unknown_cost_calls", 0) > 0:
        print(
            "WARNING: Some requests have unknown costs. "
            "The displayed total may be lower than the actual bill."
        )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run JSON Stress baseline and retry experiments."
    )

    parser.add_argument(
        "--runs-per-schema",
        type=int,
        default=40,
        help="Number of paired samples per schema (default: 40).",
    )

    parser.add_argument(
        "--only-schema",
        choices=SCHEMA_NAMES,
        default=None,
        help="Run only the specified schema (default: all schemas).",
    )

    parser.add_argument(
        "--start-sample",
        type=int,
        default=1,
        help="First sample number to run (default: 1).",
    )

    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum generation attempts for retry strategy (default: 3).",
    )

    parser.add_argument(
        "--max-total-cost-usd",
        type=float,
        default=2.0,
        help=(
            "Stop starting experiments once this run's accumulated "
            "recorded cost reaches the threshold. Unknown costs are "
            "not included."
        ),
    )

    parser.add_argument(
        "--output",
        default="results/openrouter_experiment.jsonl",
        help="Output JSONL path. Existing files are protected by default.",
    )

    parser.add_argument(
        "--overwrite-output",
        action="store_true",
        help="Allow replacing an existing output file.",
    )

    parser.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "Make one API call and validate schema_01 without "
            "running experiments."
        ),
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.runs_per_schema < 1:
        parser.error("--runs-per-schema must be at least 1.")

    if args.start_sample < 1:
        parser.error("--start-sample must be at least 1.")

    if args.max_attempts < 1:
        parser.error("--max-attempts must be at least 1.")

    if args.max_total_cost_usd <= 0:
        parser.error("--max-total-cost-usd must be greater than 0.")

    run_experiments(args)


if __name__ == "__main__":
    main()
