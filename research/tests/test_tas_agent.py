"""
Tests for tas_agent.py - verify the injected prompt is well-formed.
Run from repo root: python -m pytest research/tests/

These tests do NOT require a running Factorio server or Ollama.
"""

import ast
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from research.agents.tas_agent import build_few_shot_prompt, abstract_position


SAMPLE_TRAJECTORY = [
    {"step": 1, "action": "walk", "fle": "move_to((-2.5, 10.5))", "raw": "..."},
    {"step": 3, "action": "build", "fle": "place_entity('burner-mining-drill', direction=Direction.NORTH, position=(-1.0, 10.0))", "raw": "..."},
    {"step": 6, "action": "mine", "fle": "harvest_resource(nearest('resource', (-2.25, 9.75)))", "raw": "..."},
    {"step": 10, "action": "tech", "fle": "set_research('automation')", "raw": "..."},
    {"step": 18, "action": "craft", "fle": "craft_item('iron-gear-wheel', 3)", "raw": "..."},
]


def test_few_shot_prompt_contains_all_steps():
    prompt = build_few_shot_prompt(SAMPLE_TRAJECTORY, n=5, abstract=False)
    for entry in SAMPLE_TRAJECTORY:
        assert entry["fle"] in prompt, f"Missing step in prompt: {entry['fle']}"


def test_few_shot_respects_n_limit():
    prompt = build_few_shot_prompt(SAMPLE_TRAJECTORY, n=3, abstract=False)
    # Step 4 and 5 should not be present
    assert "iron-gear-wheel" not in prompt
    assert "automation" not in prompt


def test_abstract_mode_removes_raw_coords():
    prompt = build_few_shot_prompt(SAMPLE_TRAJECTORY, n=5, abstract=True)
    # Raw coordinate tuples should not appear literally
    assert "(-2.5, 10.5)" not in prompt
    assert "(-2.25, 9.75)" not in prompt


def test_abstract_position_move_to():
    result = abstract_position("move_to((-31.0, 7.0))")
    assert "(-31.0, 7.0)" not in result
    assert "move_to" in result


def test_abstract_position_passthrough():
    """Actions without positions should pass through unchanged."""
    call = "set_research('automation')"
    assert abstract_position(call) == call

    call = "craft_item('iron-gear-wheel', 3)"
    assert abstract_position(call) == call


def test_prompt_is_a_string():
    prompt = build_few_shot_prompt(SAMPLE_TRAJECTORY, n=5)
    assert isinstance(prompt, str)
    assert len(prompt) > 100


def test_agent_loads_from_json(tmp_path):
    """TASGroundedAgent must load trajectory from JSON without error."""
    traj_file = tmp_path / "tas_trajectory.json"
    traj_file.write_text(json.dumps(SAMPLE_TRAJECTORY))

    # We can't instantiate the full agent without a task/model,
    # but we can verify the prompt-building path works end-to-end.
    with open(traj_file) as f:
        traj = json.load(f)
    prompt = build_few_shot_prompt(traj, n=5)
    assert "automation" in prompt
