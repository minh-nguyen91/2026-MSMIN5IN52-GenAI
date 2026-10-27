
"""
Command-line interface for the JSON Stress project.

Commands:
- generate: generate and validate JSON with a retry strategy
- evaluate: evaluate an existing experiment result file
- report: generate report artifacts
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .evaluation import (
    compute_global_metrics,
    compute_metrics_by_schema,
    compute_metrics_by_strategy,
    load_results,
)
from .generator import MockGenerator
from .report import generate_full_report
from .retry import RetryManager


SCHEMA_NAMES = [
    "schema_01.json",
    "schema_02.json",
    "schema_03.json",
    "schema_04.json",
    "schema_05.json",
]


def build_parser() -> argparse.ArgumentParser:
    """Build the main command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="json-stress",
        description=(
            "JSON generation, validation, retry, "
            "evaluation and reporting."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate JSON and retry when validation fails.",
    )

    generate_parser.add_argument(
        "--schema",
        choices=SCHEMA_NAMES,
        default="schema_01.json",
        help="Schema used to validate the generated JSON.",
    )
    generate_parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum number of generation attempts (default: 3).",
    )
    generate_parser.add_argument(
        "--max-latency-ms",
        type=float,
        default=None,
        help="Optional maximum total latency in milliseconds.",
    )
    generate_parser.add_argument(
        "--max-cost",
        type=float,
        default=None,
        help="Optional maximum estimated cost.",
    )
    generate_parser.add_argument(
        "--cost-per-attempt",
        type=float,
        default=0.0,
        help="Estimated cost per attempt (default: 0).",
    )
    generate_parser.add_argument(
        "--output",
        default="results/generated_results.jsonl",
        help="JSONL file to which the result will be appended.",
    )

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="Evaluate an existing experiment result file.",
    )
    evaluate_parser.add_argument(
        "input",
        help="Path to a .jsonl or .csv result file.",
    )

    report_parser = subparsers.add_parser(
        "report",
        help="Generate CSV tables, PNG charts and a Markdown report.",
    )
    report_parser.add_argument(
        "input",
        help="Path to a .jsonl or .csv result file.",
    )
    report_parser.add_argument(
        "--output-dir",
        default="results/report",
        help="Directory where report artifacts will be written.",
    )

    return parser


def print_global_metrics(metrics: dict[str, Any]) -> None:
    """Print global evaluation metrics."""
    print("\n=== Global metrics ===")
    print(f"Total generations: {metrics['total_generations']}")
    print(
        "Initial compliance rate: "
        f"{metrics['initial_compliance_rate']:.2%}"
    )
    print(
        "Final compliance rate: "
        f"{metrics['final_compliance_rate']:.2%}"
    )
    print(
        "Final failure rate: "
        f"{metrics['final_failure_rate']:.2%}"
    )
    print(f"Average attempts: {metrics['avg_attempts']:.2f}")
    print(f"Average latency: {metrics['avg_latency_ms']:.2f} ms")
    print(f"Total cost: {metrics['total_cost']:.6f}")
    print(f"Average cost: {metrics['avg_cost']:.6f}")


def run_generate(
    schema_name: str,
    output_path: str,
    max_attempts: int = 3,
    max_latency_ms: float | None = None,
    max_cost: float | None = None,
    cost_per_attempt: float = 0.0,
) -> dict[str, Any]:
    """
    Generate one result using MockGenerator and RetryManager.

    Reject unsupported schemas before generation or writing output.
    """
    # Validate the schema before starting any generation attempts.
    if schema_name not in SCHEMA_NAMES:
        raise ValueError(f"Unsupported schema: {schema_name}")

    generator = MockGenerator()

    retry_manager = RetryManager(
        max_attempts=max_attempts,
        max_latency_ms=max_latency_ms,
        max_cost=max_cost,
        cost_per_attempt=cost_per_attempt,
    )

    result = retry_manager.run(
        generator=generator,
        schema_name=schema_name,
    )

    destination = Path(output_path)
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with destination.open("a", encoding="utf-8") as result_file:
        result_file.write(
            json.dumps(result, ensure_ascii=False) + "\n"
        )

    print("\n=== Generation result ===")
    print(f"Schema: {result['schema_id']}")
    print(f"Provider: {result['provider']}")
    print(f"Model: {result['model']}")
    print(f"Attempts: {result['attempts']}")
    print(f"First attempt valid: {result['first_try_valid']}")
    print(f"Final valid: {result['final_valid']}")
    print(f"Latency: {result['latency_ms']:.3f} ms")
    print(f"Estimated cost: {result['cost']:.6f}")
    print(f"Stop reason: {result['stop_reason']}")

    if result["data"] is not None:
        print("\nGenerated JSON:")
        print(
            json.dumps(
                result["data"],
                ensure_ascii=False,
                indent=2,
            )
        )

    if result["errors"]:
        print("\nValidation or generation errors:")
        for error in result["errors"]:
            print(
                f"- [{error.get('type', 'unknown')}] "
                f"{error.get('path', '$')}: "
                f"{error.get('message', '')}"
            )

    print(f"\nResult appended to: {destination.resolve()}")

    return result


def run_evaluate(input_path: str) -> None:
    """Load a result file and print evaluation metrics."""
    df = load_results(input_path)

    global_metrics = compute_global_metrics(df)
    by_schema = compute_metrics_by_schema(df)
    by_strategy = compute_metrics_by_strategy(df)

    print_global_metrics(global_metrics)

    print("\n=== Metrics by schema ===")
    if by_schema.empty:
        print("No data.")
    else:
        print(by_schema.to_string(index=False))

    print("\n=== Metrics by strategy ===")
    if by_strategy.empty:
        print("No data.")
    else:
        print(by_strategy.to_string(index=False))


def run_report(input_path: str, output_dir: str) -> None:
    """Generate report artifacts from an experiment result file."""
    df = load_results(input_path)

    artifacts = generate_full_report(df, output_dir)

    resolved_output = Path(output_dir).resolve()

    print("\n=== Report generated ===")
    print(f"Output directory: {resolved_output}")
    print(f"Markdown report: {artifacts['markdown_report']}")
    print(f"Compliance chart: {artifacts['compliance_chart']}")
    print(f"Strategy chart: {artifacts['strategy_chart']}")
    print(f"Latency chart: {artifacts['latency_chart']}")
    print(f"Cost chart: {artifacts['cost_chart']}")


def main() -> None:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "generate":
            run_generate(
                schema_name=args.schema,
                output_path=args.output,
                max_attempts=args.max_attempts,
                max_latency_ms=args.max_latency_ms,
                max_cost=args.max_cost,
                cost_per_attempt=args.cost_per_attempt,
            )

        elif args.command == "evaluate":
            run_evaluate(args.input)

        elif args.command == "report":
            run_report(args.input, args.output_dir)

    except (ValueError, FileNotFoundError, OSError) as exc:
        parser.exit(
            status=1,
            message=f"Error: {exc}\n",
        )


if __name__ == "__main__":
    main()
