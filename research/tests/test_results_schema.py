"""
Tests for result JSON schema - prevent summarize_results.py from silently skipping files.
Run from repo root: python -m pytest research/tests/
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


REQUIRED_TOP_LEVEL_KEYS = {
    "run_id", "model", "condition", "tas_steps_injected",
    "factorio_version", "fle_version", "date", "summary", "tasks",
}

REQUIRED_SUMMARY_KEYS = {"completed", "total", "completion_rate"}

REQUIRED_TASK_KEYS = {"completed", "score", "steps_taken"}


def validate_result(data: dict):
    """Raises AssertionError with a clear message if schema is wrong."""
    missing = REQUIRED_TOP_LEVEL_KEYS - set(data.keys())
    assert not missing, f"Result missing top-level keys: {missing}"

    summary = data["summary"]
    missing = REQUIRED_SUMMARY_KEYS - set(summary.keys())
    assert not missing, f"Result summary missing keys: {missing}"

    assert 0.0 <= summary["completion_rate"] <= 1.0, \
        f"completion_rate out of range: {summary['completion_rate']}"

    assert summary["completed"] <= summary["total"], \
        f"completed ({summary['completed']}) > total ({summary['total']})"

    for task_name, task_result in data["tasks"].items():
        missing = REQUIRED_TASK_KEYS - set(task_result.keys())
        assert not missing, f"Task '{task_name}' missing keys: {missing}"
        assert isinstance(task_result["completed"], bool), \
            f"Task '{task_name}' completed must be bool"


def test_valid_result_passes():
    valid = {
        "run_id": "test_run_001",
        "model": "ollama-qwen2.5-coder:14b",
        "condition": "zero_shot",
        "tas_steps_injected": 0,
        "factorio_version": "2.0.76",
        "fle_version": "0.4.0",
        "date": "2026-05-18T00:00:00",
        "max_steps_per_task": 50,
        "summary": {"completed": 3, "total": 24, "completion_rate": 0.125},
        "tasks": {
            "task_01": {"completed": True, "score": 1, "steps_taken": 12, "error": None},
            "task_02": {"completed": False, "score": 0, "steps_taken": 50, "error": None},
        },
    }
    validate_result(valid)  # should not raise


def test_missing_summary_key_fails():
    bad = {
        "run_id": "x", "model": "x", "condition": "x",
        "tas_steps_injected": 0, "factorio_version": "x",
        "fle_version": "x", "date": "x",
        "summary": {"completed": 1, "total": 24},  # missing completion_rate
        "tasks": {},
    }
    with pytest.raises(AssertionError, match="completion_rate"):
        validate_result(bad)


def test_all_existing_results_are_valid():
    """Validate every JSON file already in research/results/."""
    results_dir = Path("research/results")
    json_files = list(results_dir.glob("*.json"))
    if not json_files:
        pytest.skip("No result files yet")
    for f in json_files:
        data = json.loads(f.read_text())
        validate_result(data)
