
import json

import pytest

from json_stress.cli import build_parser, run_generate


def test_generate_command_arguments():
    parser = build_parser()

    args = parser.parse_args(
        [
            "generate",
            "--schema",
            "schema_02.json",
            "--max-attempts",
            "4",
            "--output",
            "results/test_results.jsonl",
        ]
    )

    assert args.command == "generate"
    assert args.schema == "schema_02.json"
    assert args.max_attempts == 4
    assert args.output == "results/test_results.jsonl"


def test_generate_writes_jsonl_result(tmp_path):
    output_file = tmp_path / "results" / "generated.jsonl"

    result = run_generate(
        schema_name="schema_01.json",
        output_path=str(output_file),
        max_attempts=3,
    )

    assert output_file.exists()
    assert result["schema_id"] == "schema_01.json"
    assert result["provider"] == "mock"
    assert result["final_valid"] is True
    assert result["attempts"] == 1

    lines = output_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    saved_result = json.loads(lines[0])
    assert saved_result["schema_id"] == "schema_01.json"
    assert saved_result["final_valid"] is True


def test_generate_appends_multiple_results(tmp_path):
    output_file = tmp_path / "generated.jsonl"

    run_generate(
        schema_name="schema_01.json",
        output_path=str(output_file),
    )
    run_generate(
        schema_name="schema_02.json",
        output_path=str(output_file),
    )

    lines = output_file.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert json.loads(lines[0])["schema_id"] == "schema_01.json"
    assert json.loads(lines[1])["schema_id"] == "schema_02.json"


def test_generate_rejects_unknown_schema(tmp_path):
    output_file = tmp_path / "generated.jsonl"

    with pytest.raises(ValueError, match="Unsupported schema"):
        run_generate(
            schema_name="unknown_schema.json",
            output_path=str(output_file),
        )

    assert not output_file.exists()


def test_generate_rejects_invalid_attempt_limit(tmp_path):
    with pytest.raises(ValueError, match="max_attempts"):
        run_generate(
            schema_name="schema_01.json",
            output_path=str(tmp_path / "generated.jsonl"),
            max_attempts=0,
        )
