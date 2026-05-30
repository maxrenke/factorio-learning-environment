"""
Tests for parse_tas.py - verify TAS step translation is correct.
Run from repo root: python -m pytest research/tests/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from research.scripts.parse_tas import to_fle, parse_coords, parse_strings


# Known step lines -> expected FLE call fragments
CASES = [
    (
        'step[3] = {{3,1}, "build", {-1.000000, 10.000000}, "burner-mining-drill", defines.direction.north}',
        ("place_entity", "burner-mining-drill", "-1.0", "10.0", "NORTH"),
    ),
    (
        # mine steps lack a resource type, so they become a comment placeholder
        # (nearest('resource', ...) is not a valid FLE call).
        'step[6] = {{6,1}, "mine", {-2.250000, 9.750000}, 1000}',
        ("# mine", "-2.25", "9.75"),
    ),
    (
        'step[10] = {{10,1}, "tech", "automation"}',
        ("set_research", "automation"),
    ),
    (
        'step[18] = {{18,1}, "craft", 3, "iron-gear-wheel"}',
        ("craft_item", "iron-gear-wheel", "3"),
    ),
    (
        'step[13] = {{13,1}, "take", {-19.000000, 1.300000}, "iron-plate", -1, defines.inventory.chest}',
        ("extract_item", "iron-plate"),
    ),
    (
        'step[5] = {{5,1}, "put", {-1.000000, 10.000000}, "wood", 1, defines.inventory.fuel}',
        ("insert_item", "wood"),
    ),
    (
        'step[2] = {{2,1}, "walk", {-2.500000, 10.500000}, "", "different_x", "different_y", walk_towards = true,}',
        ("move_to", "-2.5", "10.5"),
    ),
]


def test_step_translations():
    for line, expected_fragments in CASES:
        result = to_fle(line)
        assert result is not None, f"to_fle returned None for: {line}"
        for fragment in expected_fragments:
            assert fragment in result, (
                f"Expected '{fragment}' in result '{result}'\nInput: {line}"
            )


def test_hyphenated_item_names():
    """Item names with hyphens must be preserved exactly."""
    line = 'step[18] = {{18,1}, "craft", 3, "iron-gear-wheel"}'
    result = to_fle(line)
    assert "iron-gear-wheel" in result, f"Hyphenated name mangled: {result}"


def test_negative_coords():
    """Negative coordinates must parse correctly."""
    line = 'step[9] = {{9,1}, "walk", {-31.000000, 7.000000}, "", "different_x", "different_y", walk_towards = true,}'
    result = to_fle(line)
    assert "-31.0" in result, f"Negative coordinate lost: {result}"


def test_speed_and_save_return_none():
    """Control-flow steps should not produce FLE calls."""
    for action in ['"speed"', '"save"', '"pause"']:
        line = f'step[1] = {{{{1,1}}, {action}, 1}}'
        result = to_fle(line)
        assert result is None, f"Expected None for {action}, got: {result}"


def test_no_broken_placeholders_in_output():
    """No output should contain raw placeholder strings that aren't valid Python identifiers."""
    bad_fragments = ["<nearest", "<adjacent", "<build site"]
    for line, _ in CASES:
        result = to_fle(line)
        if result:
            for bad in bad_fragments:
                assert bad not in result, (
                    f"Broken placeholder '{bad}' found in: {result}"
                )
